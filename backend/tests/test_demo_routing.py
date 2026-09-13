"""
Regression test for a real bug found during a data-cleanup pass: execute_pipeline()
used to decide "is this a bundled demo project" purely by checking whether a
file named project_{id}_before.png happened to exist on disk (demo assets are
named only by ID: project_1_before.png ... project_6_before.png). A REAL
project that happened to land on database ID 1-6 — e.g. in any fresh/isolated
database where demo data isn't seeded first — would be silently misrouted
into the demo pipeline instead of its actual evidence pipeline, and could
crash outright if it had no coordinates (the demo path assumes lat/lon always
exist). The fix gates on the project's actual `is_demo` flag first.

This test uses its own freshly-created empty database so the very first
project inserted gets ID 1 — deliberately colliding with a bundled demo asset
filename — and confirms a REAL, non-demo project on that ID is still
analyzed via its real (manual-evidence) pipeline, not the demo one. The
satellite-service HTTP call is mocked (no network needed), consistent with
the rest of the suite.
"""
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["DATABASE_URL"] = "sqlite:///./test_demo_routing.db"
os.environ["SATELLITE_MODE"] = "demo"

import pytest

from app.main import app  # noqa: F401 (import triggers table creation)
from app.database import Base, engine, SessionLocal
from app.models.models import Project, SatelliteObservation
from app.api import projects as projects_api


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    engine.dispose()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_demo_routing.db"):
        try:
            os.remove("./test_demo_routing.db")
        except PermissionError:
            pass


def test_real_project_on_a_demo_asset_id_is_not_routed_to_demo_pipeline(monkeypatch):
    fake_raw = {
        "observable_change_percent": 12.3,
        "changed_pixel_count": 1000,
        "total_pixel_count": 262144,
        "candidate_count": 2,
        "candidates": [{"bbox": [0, 0, 10, 10]}, {"bbox": [20, 20, 5, 5]}],
        "geojson_overlay": {"type": "FeatureCollection", "features": []},
        "model_version": "planaura-resnet18-featurediff-v1 (manual-upload, no-NDVI)",
    }
    monkeypatch.setattr(projects_api, "manual_detect_images", lambda *a, **kw: fake_raw)

    db = SessionLocal()
    try:
        # First project in this fresh DB -> id=1, which collides with
        # app/demo_assets/project_1_before.png. is_demo=0 (a real project)
        # must win over that filename coincidence.
        project = Project(
            name="Real project landing on a demo-asset ID",
            project_type="Roads",
            description="",
            latitude=None,
            longitude=None,
            reported_progress=0.0,
            status="normal",
            is_demo=0,
            evidence_source="manual_upload",
        )
        db.add(project)
        db.flush()
        assert project.id == 1  # sanity check the collision actually applies

        now = datetime.now(timezone.utc)
        db.add_all([
            SatelliteObservation(
                project_id=project.id, acquisition_date=now, source="manual-upload",
                image_reference="tamil-udayarpalayam/before.jpeg", processing_status="ready",
            ),
            SatelliteObservation(
                project_id=project.id, acquisition_date=now, source="manual-upload",
                image_reference="tamil-udayarpalayam/after.jpeg", processing_status="ready",
            ),
        ])
        db.commit()

        result = projects_api.execute_pipeline(project, db)
        assert result.t1_scene.source == "manual-upload"
        assert result.t2_scene.source == "manual-upload"
        assert result.observable_change_percent == 12.3
    finally:
        db.close()
