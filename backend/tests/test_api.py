import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Use an isolated, disposable SQLite DB for tests so we never touch a dev DB.
os.environ["DATABASE_URL"] = "sqlite:///./test_infrawatch.db"

import pytest
from datetime import datetime
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, engine, SessionLocal
from app.models.models import Project, SatelliteObservation


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    engine.dispose()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add(Project(
        name="[TEST] Test Project", project_type="Roads", description="test",
        latitude=28.5, longitude=77.5, geometry_wkt="POINT(77.5 28.5)",
        start_date=datetime(2024, 1, 1), expected_end_date=datetime(2025, 1, 1),
        approved_cost=1000000, reported_progress=50.0, status="watch", is_demo=0,
    ))
    db.flush()
    db.add_all([
        SatelliteObservation(project_id=1, acquisition_date=datetime(2024, 1, 1),
                             source="sentinel-2-l2a", image_reference="project_1_before.png", processing_status="ready"),
        SatelliteObservation(project_id=1, acquisition_date=datetime(2025, 1, 1),
                             source="sentinel-2-l2a", image_reference="project_1_after.png", processing_status="ready"),
    ])
    db.commit()
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_infrawatch.db"):
        try:
            os.remove("./test_infrawatch.db")
        except PermissionError:
            pass


client = TestClient(app)


@pytest.fixture(scope="module")
def auth_headers():
    """Reads of the project registry require any logged-in account (analyst
    or contractor) — register a throwaway analyst once per test module."""
    register = client.post(
        "/api/auth/register",
        json={
            "email": "analyst-reader@test.local", "password": "testpass123",
            "role": "analyst", "full_name": "Test Analyst",
        },
    )
    assert register.status_code == 201
    token = register.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"


def test_list_projects_requires_auth():
    resp = client.get("/api/projects")
    assert resp.status_code == 401


def test_list_projects(auth_headers):
    resp = client.get("/api/projects", headers=auth_headers)
    assert resp.status_code == 200
    projects = resp.json()
    assert len(projects) == 1
    assert projects[0]["name"] == "[TEST] Test Project"


def test_get_project_detail(auth_headers):
    resp = client.get("/api/projects/1", headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_type"] == "Roads"
    assert body["approved_cost"] == 1000000


def _fake_pipeline_response(project_id: str) -> dict:
    """Shaped like satellite-service's real /pipeline/run JSON response."""
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
        "observable_change_percent": 6.5,
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


def test_analysis_api_workflow(auth_headers):
    with patch(
        "app.api.projects.satellite_service_run_pipeline",
        return_value=_fake_pipeline_response("1"),
    ):
        analysis = client.post("/api/projects/1/analyze", headers=auth_headers)
    assert analysis.status_code == 200
    body = analysis.json()
    assert "t1_scene" in body
    assert "t2_scene" in body
    assert "geojson_overlay" in body
    assert body["geojson_overlay"]["type"] == "FeatureCollection"


def test_create_project():
    register = client.post(
        "/api/auth/register",
        json={
            "email": "contractor1@test.local", "password": "testpass123",
            "role": "contractor", "full_name": "Test Contractor",
        },
    )
    assert register.status_code == 201
    token = register.json()["access_token"]

    resp = client.post(
        "/api/projects",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "[TEST] Created Project",
            "project_type": "Roads",
            "latitude": 28.6,
            "longitude": 77.2,
            "reported_progress": 42.0,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "[TEST] Created Project"
    assert body["is_demo"] is False
    assert body["status"] == "normal"

    listed = client.get("/api/projects", headers={"Authorization": f"Bearer {token}"}).json()
    assert any(p["id"] == body["id"] for p in listed)
