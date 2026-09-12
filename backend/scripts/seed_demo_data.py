"""
Seed the database with real satellite imagery telemetry, Gemini 2.5 Flash-Lite reasoning, and GeoJSON overlays.
Run with:

    python -m scripts.seed_demo_data

Re-running clears and re-seeds (idempotent for local dev).
"""
import sys
import os
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import Base, engine, SessionLocal
from app.models.models import (
    AIResult, Anomaly, AuditLog, FinancialRecord, Milestone, ProgressReport, Project, SatelliteObservation,
)
from app.api.projects import execute_pipeline

DEMO_PROJECTS = [
    dict(name="[DEMO] Community Health Sub-Centre, Rampur", project_type="Healthcare",
         description="Construction of a 2-room primary health sub-centre.",
         latitude=28.4744, longitude=77.5040, start_date=datetime(2024, 4, 1),
         expected_end_date=datetime(2025, 10, 1), approved_cost=4200000,
         reported_progress=82.0, status="normal"),
    dict(name="[DEMO] Government Primary School Extension, Bhatta", project_type="Education",
         description="Two additional classrooms and a boundary wall.",
         latitude=28.4530, longitude=77.5310, start_date=datetime(2024, 1, 15),
         expected_end_date=datetime(2025, 1, 15), approved_cost=1800000,
         reported_progress=92.0, status="least"),
    dict(name="[DEMO] Village Link Road, Sherpur", project_type="Roads",
         description="1.2 km all-weather link road with drainage.",
         latitude=28.4901, longitude=77.4870, start_date=datetime(2024, 6, 1),
         expected_end_date=datetime(2025, 6, 1), approved_cost=6500000,
         reported_progress=48.0, status="medium"),
    dict(name="[DEMO] Community Water Tank, Chandpur", project_type="Water Supply",
         description="Overhead water tank with distribution pipeline.",
         latitude=28.4655, longitude=77.5195, start_date=datetime(2024, 3, 1),
         expected_end_date=datetime(2024, 12, 1), approved_cost=2900000,
         reported_progress=100.0, status="normal"),
    dict(name="[DEMO] Panchayat Bhawan Renovation, Kotla", project_type="Public Buildings",
         description="Renovation and solar power fitting for panchayat office.",
         latitude=28.5012, longitude=77.4995, start_date=datetime(2024, 7, 1),
         expected_end_date=datetime(2025, 4, 1), approved_cost=1500000,
         reported_progress=40.0, status="least"),
    dict(name="[DEMO] Rural Sports Ground Development, Nangla", project_type="Sports & Recreation",
         description="Levelling, boundary fencing and pavilion construction.",
         latitude=28.4388, longitude=77.5120, start_date=datetime(2024, 2, 1),
         expected_end_date=datetime(2025, 2, 1), approved_cost=2200000,
         reported_progress=68.0, status="medium"),
]


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        existing = db.query(Project).count()
        if existing:
            print(f"Clearing {existing} existing project(s) before re-seeding...")
            db.query(AIResult).delete()
            db.query(Anomaly).delete()
            db.query(AuditLog).delete()
            db.query(SatelliteObservation).delete()
            db.query(Milestone).delete()
            db.query(FinancialRecord).delete()
            db.query(ProgressReport).delete()
            db.query(Project).delete()
            db.commit()

        for index, data in enumerate(DEMO_PROJECTS, start=1):
            geometry_wkt = f"POINT({data['longitude']} {data['latitude']})"
            project = Project(**data, geometry_wkt=geometry_wkt, is_demo=1)
            db.add(project)
            db.flush()

            # Execute dynamic pipeline for each demo project
            print(f"Executing AI-first satellite pipeline for Project #{index}: {data['name']}...")
            res = execute_pipeline(project, db)

            db.add_all([
                Milestone(project_id=project.id, milestone_date=datetime(2024, 6, 1),
                          expected_progress=30.0, description="Phase 1: Site preparation & foundation"),
                Milestone(project_id=project.id, milestone_date=datetime(2024, 12, 1),
                          expected_progress=70.0, description="Phase 2: Superstructure & roofing"),
                Milestone(project_id=project.id, milestone_date=datetime(2025, 3, 1),
                          expected_progress=100.0, description="Phase 3: Finishing & commissioning"),
                FinancialRecord(project_id=project.id, date=datetime(2024, 4, 15),
                                amount=data['approved_cost'] * 0.3, category="Initial Disbursement"),
                FinancialRecord(project_id=project.id, date=datetime(2024, 10, 1),
                                amount=data['approved_cost'] * 0.4, category="Milestone Progress Payment"),
            ])
            db.commit()
            print(
                f"  -> Project #{project.id} ready: T1={res.t1_scene.acquisition_date.date()} ({res.t1_scene.source}), "
                f"T2={res.t2_scene.acquisition_date.date()} ({res.t2_scene.source}), Candidates={res.candidate_count}"
            )

        print(f"\nSuccessfully seeded {len(DEMO_PROJECTS)} projects with real satellite imagery and AI pipeline!")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
