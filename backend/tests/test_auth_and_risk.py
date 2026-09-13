"""
Tests for authentication (register/login/role enforcement) and the risk
engine (deterministic scoring — no per-project hardcoding, unlike the old
New1 branch's `check_manual_project`/`check_small_scale_exception`).
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["DATABASE_URL"] = "sqlite:///./test_auth_risk.db"

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, engine
from app import risk_engine


@pytest.fixture(scope="module", autouse=True)
def setup_db():
    engine.dispose()
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if os.path.exists("./test_auth_risk.db"):
        try:
            os.remove("./test_auth_risk.db")
        except PermissionError:
            pass


client = TestClient(app)


# ── Auth ─────────────────────────────────────────────────────────────────

def test_register_and_login():
    reg = client.post("/api/auth/register", json={
        "email": "analyst1@test.local", "password": "correcthorse123",
        "role": "analyst", "full_name": "Analyst One",
    })
    assert reg.status_code == 201
    assert reg.json()["user"]["role"] == "analyst"
    assert "access_token" in reg.json()

    login = client.post("/api/auth/login", json={
        "email": "analyst1@test.local", "password": "correcthorse123",
    })
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["email"] == "analyst1@test.local"


def test_login_wrong_password_rejected():
    client.post("/api/auth/register", json={
        "email": "analyst2@test.local", "password": "correctpassword",
        "role": "analyst", "full_name": "Analyst Two",
    })
    resp = client.post("/api/auth/login", json={
        "email": "analyst2@test.local", "password": "wrongpassword",
    })
    assert resp.status_code == 401


def test_password_is_hashed_not_plaintext():
    from app.database import SessionLocal
    from app.models.models import User

    client.post("/api/auth/register", json={
        "email": "hashcheck@test.local", "password": "supersecretpassword",
        "role": "contractor", "full_name": "Hash Check",
    })
    db = SessionLocal()
    user = db.query(User).filter(User.email == "hashcheck@test.local").first()
    db.close()
    assert user.hashed_password != "supersecretpassword"
    assert user.hashed_password.startswith("$2b$")  # bcrypt prefix


def test_duplicate_registration_rejected():
    payload = {"email": "dupe@test.local", "password": "password123", "role": "analyst", "full_name": "Dupe"}
    first = client.post("/api/auth/register", json=payload)
    assert first.status_code == 201
    second = client.post("/api/auth/register", json=payload)
    assert second.status_code == 409


def test_project_creation_requires_contractor_role():
    reg = client.post("/api/auth/register", json={
        "email": "analyst3@test.local", "password": "password123",
        "role": "analyst", "full_name": "Analyst Three",
    })
    token = reg.json()["access_token"]
    resp = client.post(
        "/api/projects", headers={"Authorization": f"Bearer {token}"},
        json={"name": "X", "project_type": "Roads", "latitude": 1.0, "longitude": 1.0},
    )
    assert resp.status_code == 403


def test_project_creation_requires_auth_at_all():
    resp = client.post(
        "/api/projects", json={"name": "X", "project_type": "Roads", "latitude": 1.0, "longitude": 1.0},
    )
    assert resp.status_code == 401


# ── Risk engine (unit-level, no hardcoded IDs anywhere) ──────────────────

def test_cost_overrun_risk_scales_with_overrun():
    no_overrun = risk_engine.compute_cost_overrun_risk(1_000_000, 1_020_000)
    assert no_overrun.risk_score == 0.0

    big_overrun = risk_engine.compute_cost_overrun_risk(1_000_000, 1_800_000)
    assert big_overrun.risk_score > 50.0

    missing_data = risk_engine.compute_cost_overrun_risk(None, None)
    assert missing_data.risk_score == 0.0
    assert missing_data.has_data is False


def test_timeline_risk_flags_delay():
    on_time = risk_engine.compute_timeline_risk(
        start_date=datetime(2024, 1, 1), expected_end_date=datetime(2030, 1, 1), reported_progress=10.0,
    )
    assert on_time.risk_score == 0.0

    delayed = risk_engine.compute_timeline_risk(
        start_date=datetime(2020, 1, 1), expected_end_date=datetime(2021, 1, 1), reported_progress=10.0,
        reference_date=datetime(2023, 1, 1),
    )
    assert delayed.risk_score > 50.0
    assert delayed.is_delayed is True


def test_satellite_discrepancy_no_hardcoded_project_ids():
    """The old New1 branch hardcoded specific project IDs to force 0% risk
    regardless of computed values. This engine takes no project ID at all —
    it can't special-case anything even if someone tried."""
    import inspect
    sig = inspect.signature(risk_engine.compute_satellite_discrepancy_risk)
    assert "project_id" not in sig.parameters

    high_discrepancy = risk_engine.compute_satellite_discrepancy_risk(
        reported_progress=90.0, observed_change=5.0, evidence_type="satellite",
    )
    assert high_discrepancy.risk_score > 60.0

    concordant = risk_engine.compute_satellite_discrepancy_risk(
        reported_progress=50.0, observed_change=48.0, evidence_type="satellite",
    )
    assert concordant.risk_score < 10.0


def test_satellite_discrepancy_confidence_not_capped_for_real_evidence():
    """Regression test for a real bug: this used to check evidence_type ==
    "real_satellite", a value the actual caller (Project.evidence_source)
    never sets — it always passes "satellite" — so every risk assessment,
    even genuinely real-satellite-sourced ones, silently had its confidence
    capped at 0.45 as if it were low-quality evidence."""
    real_satellite = risk_engine.compute_satellite_discrepancy_risk(
        reported_progress=80.0, observed_change=75.0, satellite_confidence=0.9, evidence_type="satellite",
    )
    assert real_satellite.is_real_satellite is True
    assert real_satellite.confidence > 0.45

    manual_upload = risk_engine.compute_satellite_discrepancy_risk(
        reported_progress=80.0, observed_change=75.0, satellite_confidence=0.9, evidence_type="manual_upload",
    )
    assert manual_upload.is_real_satellite is False
    assert manual_upload.confidence <= 0.45


def test_composite_risk_never_exceeds_100_and_has_no_id_overrides():
    result = risk_engine.evaluate_project_risk(
        project_id="999999",  # arbitrary — proves no special-casing by ID
        sanctioned_amount=1_000_000, actual_expenditure=5_000_000,
        start_date=datetime(2018, 1, 1), expected_end_date=datetime(2019, 1, 1),
        reported_progress=95.0, observed_change=2.0, evidence_type="satellite",
    )
    assert 0.0 <= result.risk_score <= 100.0
    assert result.risk_level in ("LOW", "MEDIUM", "HIGH", "CRITICAL")
    assert result.risk_level == "CRITICAL"  # large overrun + delay + huge satellite discrepancy


def test_risk_endpoint_returns_breakdown():
    reg = client.post("/api/auth/register", json={
        "email": "riskcheck@test.local", "password": "password123",
        "role": "contractor", "full_name": "Risk Check",
    })
    token = reg.json()["access_token"]
    created = client.post(
        "/api/projects", headers={"Authorization": f"Bearer {token}"},
        json={"name": "[TEST] Risk Project", "project_type": "Roads", "latitude": 12.0, "longitude": 77.0},
    )
    project_id = created.json()["id"]
    resp = client.get(f"/api/projects/{project_id}/risk", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    body = resp.json()
    assert "risk_score" in body
    assert "risk_level" in body
    assert len(body["factors"]) == 4
