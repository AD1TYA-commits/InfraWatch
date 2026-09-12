import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Use an isolated, disposable SQLite DB for tests so we never touch a dev DB.
os.environ["DATABASE_URL"] = "sqlite:///./test_infrawatch.db"
os.environ["SATELLITE_MODE"] = "demo"

import pytest
from datetime import datetime, timezone
import numpy as np
from rasterio.transform import from_bounds
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, engine, SessionLocal
from app.models.models import Project, SatelliteObservation
from app.satellite_provider import EsriProvider, SatelliteScene
from app.change_detector import ChangeDetector
from app.geo_processor import ChangeGeoProcessor
from app.change_analyzer import SatelliteChangeAnalyzer


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    engine.dispose()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    db.add(Project(
        name="[DEMO] Test Project", project_type="Roads", description="test",
        latitude=28.5, longitude=77.5, geometry_wkt="POINT(77.5 28.5)",
        start_date=datetime(2024, 1, 1), expected_end_date=datetime(2025, 1, 1),
        approved_cost=1000000, reported_progress=50.0, status="watch", is_demo=1,
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


def test_health():
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["database"] == "connected"


def test_list_projects():
    resp = client.get("/api/projects")
    assert resp.status_code == 200
    projects = resp.json()
    assert len(projects) == 1
    assert projects[0]["name"] == "[DEMO] Test Project"


def test_get_project_detail():
    resp = client.get("/api/projects/1")
    assert resp.status_code == 200
    body = resp.json()
    assert body["project_type"] == "Roads"
    assert body["approved_cost"] == 1000000


def test_esri_provider_fallback():
    provider = EsriProvider()
    t1, t2 = provider.get_scene_pair(28.5, 77.5)
    assert t1.source == "esri-world-imagery-fallback"
    assert t2.source == "esri-world-imagery-fallback"
    assert t1.crs == "EPSG:4326"


def test_change_detector_and_geojson_conversion(tmp_path):
    detector = ChangeDetector(min_cv_confidence=0.1)
    t1_arr = np.zeros((512, 512, 3), dtype=np.uint8)
    t2_arr = np.zeros((512, 512, 3), dtype=np.uint8)
    # Add synthetic change rectangle
    t2_arr[100:200, 100:200] = 255

    output = detector.detect(t1_arr, t2_arr, project_id=99, asset_dir=tmp_path)
    assert len(output.candidates) > 0
    cand = output.candidates[0]
    assert cand.bbox[2] > 0 and cand.bbox[3] > 0

    # Convert to GeoJSON EPSG:4326
    transform = from_bounds(77.48, 28.48, 77.52, 28.52, 512, 512)
    geo_proc = ChangeGeoProcessor()
    geojson = geo_proc.candidates_to_geojson([cand], transform=transform)

    assert geojson["type"] == "FeatureCollection"
    assert len(geojson["features"]) == 1
    feat = geojson["features"][0]
    assert feat["geometry"]["type"] == "Polygon"
    assert len(feat["geometry"]["coordinates"][0]) == 5


def test_ai_analyzer_fallback():
    analyzer = SatelliteChangeAnalyzer()
    res = analyzer.analyze_candidates(
        crops=[],
        t1_date=datetime.now(timezone.utc),
        t2_date=datetime.now(timezone.utc),
    )
    assert res.analysis.change_detected is False
    assert res.usage.model == analyzer.model_name


def test_analysis_api_workflow():
    analysis = client.post("/api/projects/1/analyze")
    assert analysis.status_code == 200
    body = analysis.json()
    assert "t1_scene" in body
    assert "t2_scene" in body
    assert "geojson_overlay" in body
    assert body["geojson_overlay"]["type"] == "FeatureCollection"
