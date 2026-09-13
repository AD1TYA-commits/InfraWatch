"""
Seeds the real, government-sourced MPLADS legacy-evidence projects directly
into the database (same direct-DB pattern as scripts/seed_demo_data.py — no
HTTP round trips).

Source CSV: backend/data/processed/mplads_normalized.csv (1,000 real
MoSPI/SBI MPLADS records — see docs/MERGE-NOTES.md for full provenance).
That CSV is a *sanction/works registry*, not a live construction tracker:
997 of its 1,000 rows have no GPS coordinate and no real self-reported
progress figure at all, so importing all 1,000 as individual "projects"
would mean fabricating a misleading 0% progress for records that simply
don't carry that data. Instead, this script pulls out only the 3 rows that
DO have a government-verified GPS coordinate — which are exactly the 3 rows
with real manually-photographed before/after evidence — and leaves the rest
of the CSV as reference data on disk, not registry entries.

Seeds 4 real legacy projects total with manually-photographed before/after
evidence (backend/app/manual_evidence/): 3 sourced from the CSV rows above
(Goa Joggers Park, Goa Seraulim Crematorium, Nagaland Forest Colony Pond —
real coordinate, used only for map placement) plus 1 standalone example not
in the CSV at all (Tamil Nadu Udayarpalayam, no coordinate). All 4 are
scored by the real change-detection model via manual-evidence upload, not a
satellite pass — see docs/MERGE-NOTES.md for why.

Usage:
    python -m scripts.seed_real_mplads
"""
import csv
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import SessionLocal
from app.models.models import Project, SatelliteObservation
from app.api.projects import execute_pipeline

CSV_PATH = Path(__file__).resolve().parents[1] / "data" / "processed" / "mplads_normalized.csv"

# work_id -> manual_evidence/ subfolder (already deduped real photos — see
# docs/MERGE-NOTES.md for where these came from and why they're kept).
MANUAL_EVIDENCE_FOR_CSV_ROWS = {
    "MPLADS-GA-3114C6BB": "goa-seraulim-crematorium",
    "MPLADS-GA-2CC4491C": "goa-joggers-park",
    "MPLADS-NL-D374AE9F": "forest-colony-pond",
}


def _parse_float(value):
    try:
        return float(value) if value not in (None, "") else None
    except ValueError:
        return None


def _parse_date(value):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None


def _attach_manual_evidence(db, project: Project, slug: str):
    project.evidence_source = "manual_upload"
    db.query(SatelliteObservation).filter(
        SatelliteObservation.project_id == project.id, SatelliteObservation.source == "manual-upload"
    ).delete()
    now = datetime.now(timezone.utc)
    before_ext = "jpeg" if slug == "tamil-udayarpalayam" else "png"
    db.add_all([
        SatelliteObservation(
            project_id=project.id, acquisition_date=now, source="manual-upload",
            image_reference=f"{slug}/before.{before_ext}", processing_status="ready",
        ),
        SatelliteObservation(
            project_id=project.id, acquisition_date=now, source="manual-upload",
            image_reference=f"{slug}/after.{before_ext}", processing_status="ready",
        ),
    ])


def seed():
    if not CSV_PATH.exists():
        print(f"CSV not found at {CSV_PATH} — nothing to import.")
        return

    db = SessionLocal()
    try:
        with open(CSV_PATH, newline="") as f:
            rows = list(csv.DictReader(f))
        csv_rows_by_work_id = {r.get("work_id"): r for r in rows}

        manual_evidence_projects = []  # (Project, slug) pairs to analyze at the end

        print(f"Seeding {len(MANUAL_EVIDENCE_FOR_CSV_ROWS)} real MPLADS project(s) with a verified "
              f"GPS coordinate from {CSV_PATH.name} (the other {len(rows) - len(MANUAL_EVIDENCE_FOR_CSV_ROWS)} "
              "rows in that CSV have no coordinate and no real progress figure, so they're left as "
              "reference data on disk rather than fabricated registry entries)...")

        for work_id, slug in MANUAL_EVIDENCE_FOR_CSV_ROWS.items():
            row = csv_rows_by_work_id.get(work_id)
            if row is None:
                print(f"  WARNING: work_id {work_id} not found in CSV — skipping.")
                continue
            lat, lon = _parse_float(row.get("latitude")), _parse_float(row.get("longitude"))
            project = Project(
                name=row["name"][:250],
                project_type=row.get("project_type") or "Public Works",
                description=(row.get("description") or "")[:1000],
                latitude=lat,
                longitude=lon,
                geometry_wkt=f"POINT({lon} {lat})" if lat is not None and lon is not None else None,
                start_date=_parse_date(row.get("start_date")),
                expected_end_date=_parse_date(row.get("expected_end_date")),
                approved_cost=_parse_float(row.get("sanctioned_amount")),
                reported_progress=_parse_float(row.get("reported_progress")) or 0.0,
                status="normal",
                is_demo=0,
                evidence_source="manual_upload",
                work_id=work_id,
                mp_name=row.get("mp_name"),
                state_name=row.get("state_name"),
                constituency_name=row.get("constituency_name"),
                district_name=row.get("district_name"),
                implementing_agency=row.get("implementing_agency"),
                sanctioned_amount=_parse_float(row.get("sanctioned_amount")),
                actual_expenditure=_parse_float(row.get("actual_expenditure")),
                data_source=row.get("data_source") or "india-mplads-works",
            )
            db.add(project)
            db.flush()  # assigns project.id without a full commit
            manual_evidence_projects.append((project, slug))

        db.commit()

        # The 4th manual-evidence project isn't in the MPLADS CSV at all.
        tamil = Project(
            name="Construction/upgrade works, Udayarpalayam",
            project_type="Public Works",
            description=(
                "Real-world example project supplied with manually-photographed "
                "before/after evidence (no GPS coordinate on record)."
            ),
            latitude=None, longitude=None, geometry_wkt=None,
            reported_progress=0.0, status="normal", is_demo=0,
            evidence_source="manual_upload",
            work_id="INFRAWATCH-TN-UDAYARPALAYAM-2025",
            state_name="Tamil Nadu", district_name="Ariyalur",
            data_source="manual-field-evidence",
        )
        db.add(tamil)
        db.flush()
        manual_evidence_projects.append((tamil, "tamil-udayarpalayam"))
        db.commit()

        print(f"\nAttaching manual before/after evidence to {len(manual_evidence_projects)} project(s) "
              "and running real model-based detection on each (PlanAura, via satellite-service)...")
        for project, slug in manual_evidence_projects:
            _attach_manual_evidence(db, project, slug)
            db.commit()
            try:
                result = execute_pipeline(project, db)
                print(f"  #{project.id} ({slug}): {result.observable_change_percent}% change, {result.candidate_count} regions")
            except Exception as exc:
                print(f"  #{project.id} ({slug}) FAILED: {exc}")

        print("\nDone.")
    finally:
        db.close()


if __name__ == "__main__":
    seed()
