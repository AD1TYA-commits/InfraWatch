"""
Tests for the satellite-service integration layer: the HTTP client wrapper,
the adapter that turns its response into InfraWatch's own DB rows/schema, and
the dashboard's `latest_image_url` convenience field.

These mock the network call entirely (no real satellite-service or internet
access needed) — they exist to catch integration-shape regressions like the
datetime-string bug fixed during the real end-to-end test, not to re-test
satellite-service's own logic (that's covered in its own repo).
"""
import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["DATABASE_URL"] = "sqlite:///./test_satellite_integration.db"

import pytest
import httpx
from datetime import datetime

from app.database import Base, engine, SessionLocal
from app.models.models import Project, SatelliteObservation
from app.api.projects import _execute_via_satellite_service, list_projects
from app.satellite_service_client import run_pipeline, SatelliteServiceError


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    engine.dispose()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_satellite_integration.db"):
        try:
            os.remove("./test_satellite_integration.db")
        except PermissionError:
            pass


def _fake_pipeline_response(project_id: str, observable_change_percent: float = 6.5) -> dict:
    """Shaped exactly like satellite-service's real /pipeline/run JSON response
    (dates as ISO strings — that's the field that broke SQLAlchemy)."""
    return {
        "project_id": project_id,
        "t1_scene": {
            "scene_id": "S2A_TEST_T1", "acquisition_date": "2026-01-01T05:00:00+00:00",
            "cloud_percentage": 1.2, "bbox": [77.0, 28.0, 77.1, 28.1],
        },
        "t2_scene": {
            "scene_id": "S2B_TEST_T2", "acquisition_date": "2026-06-01T05:00:00+00:00",
            "cloud_percentage": 2.4, "bbox": [77.0, 28.0, 77.1, 28.1],
        },
        "observable_change_percent": observable_change_percent,
        "changed_pixel_count": 1200,
        "total_pixel_count": 65536,
        "candidate_count": 1,
        "candidates": [
            {"candidate_id": "candidate-001", "bbox": [10, 10, 40, 40], "pixel_area": 1200,
             "estimated_area_m2": 120000.0, "confidence": 0.72, "type_hint": "built_up_or_construction"},
        ],
        "geojson_overlay": {"type": "FeatureCollection", "features": []},
        "before_image_path": f"data/T1/{project_id}/true_color.png",
        "after_image_path": f"data/T2/{project_id}/true_color.png",
        "mask_image_path": f"data/T2/{project_id}/change_mask.png",
        "explanation": {
            "change_detected": True, "confidence": 0.72,
            "summary": "Detected construction-like change.",
            "changes": [{"type": "built_up_or_construction", "confidence": 0.72, "description": "test change"}],
            "narrated_by": "template-fallback",
        },
        "model_version": "planaura-resnet18-featurediff-v1",
        "error": None,
    }


def _make_project(db, **overrides) -> Project:
    defaults = dict(
        name="[TEST] Real-mode Project", project_type="Roads", description="test",
        latitude=28.5, longitude=77.5, geometry_wkt="POINT(77.5 28.5)",
        reported_progress=82.0, status="normal", is_demo=0,
    )
    defaults.update(overrides)
    project = Project(**defaults)
    db.add(project)
    db.flush()
    return project


def test_run_pipeline_client_success(monkeypatch):
    class FakeResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return _fake_pipeline_response("42")

    def fake_post(url, json, timeout):
        assert url.endswith("/pipeline/run")
        assert json["project_id"] == "42"
        return FakeResponse()

    monkeypatch.setattr(httpx, "post", fake_post)
    result = run_pipeline(project_id=42, name="X", latitude=1.0, longitude=2.0,
                           project_type="Roads", reported_progress=50.0)
    assert result["project_id"] == "42"


def test_run_pipeline_client_wraps_transport_errors(monkeypatch):
    def fake_post(*args, **kwargs):
        raise httpx.ConnectError("connection refused")

    monkeypatch.setattr(httpx, "post", fake_post)
    with pytest.raises(SatelliteServiceError):
        run_pipeline(project_id=1, name="X", latitude=1.0, longitude=2.0,
                      project_type="Roads", reported_progress=50.0)


def test_execute_via_satellite_service_parses_dates_and_writes_db():
    """Regression test for the bug caught in real end-to-end testing: satellite-service
    returns acquisition_date as an ISO string, which SQLAlchemy's DateTime column
    rejects unless explicitly parsed to a real datetime first."""
    db = SessionLocal()
    try:
        project = _make_project(db, reported_progress=82.0)
        db.commit()

        with patch(
            "app.api.projects.satellite_service_run_pipeline",
            return_value=_fake_pipeline_response(str(project.id), observable_change_percent=1.0),
        ):
            result = _execute_via_satellite_service(project, db, start_time=0.0)

        assert result.t1_scene.acquisition_date == datetime.fromisoformat("2026-01-01T05:00:00+00:00")
        assert result.recommendation == "Field verification recommended"  # 82% reported vs 1% observed
        assert result.candidate_count == 1
        assert result.geojson_overlay == {"type": "FeatureCollection", "features": []}

        obs = db.query(SatelliteObservation).filter(SatelliteObservation.project_id == project.id).all()
        assert len(obs) == 2
        assert all(isinstance(o.acquisition_date, datetime) for o in obs)
    finally:
        db.close()


def test_execute_via_satellite_service_degrades_gracefully_on_failure():
    db = SessionLocal()
    try:
        project = _make_project(db, name="[TEST] Unreachable service")
        db.commit()

        with patch(
            "app.api.projects.satellite_service_run_pipeline",
            side_effect=SatelliteServiceError("satellite-service call failed: connection refused"),
        ):
            result = _execute_via_satellite_service(project, db, start_time=0.0)

        assert "connection refused" in result.explanation
        assert result.candidate_count == 0
        assert project.status == "watch"
    finally:
        db.close()


def test_list_projects_exposes_latest_image_url_for_both_source_kinds():
    db = SessionLocal()
    try:
        manual_project = _make_project(db, name="[TEST] Manual-upload project")
        real_project = _make_project(db, name="[TEST] Satellite-service project")
        db.flush()

        db.add(SatelliteObservation(
            project_id=manual_project.id, acquisition_date=datetime(2024, 1, 1),
            source="manual-upload", image_reference=f"{manual_project.id}/after.png",
            processing_status="ready",
        ))
        db.add(SatelliteObservation(
            project_id=real_project.id, acquisition_date=datetime(2026, 1, 1),
            source="sentinel-2-l2a (satellite-service)",
            image_reference=f"data/T2/{real_project.id}/true_color.png",
            processing_status="ready",
        ))
        db.commit()

        summaries = {p.id: p for p in list_projects(db, current_user=None)}

        assert summaries[manual_project.id].latest_image_url == f"/manual-evidence/{manual_project.id}/after.png"
        assert summaries[real_project.id].latest_image_url.startswith("http")
        assert summaries[real_project.id].latest_image_url.endswith(f"data/T2/{real_project.id}/true_color.png")
    finally:
        db.close()
