"""
Seeds the real, government-sourced MPLADS dataset directly into the database
(same direct-DB pattern as scripts/seed_demo_data.py — no HTTP round trips,
so 1,000 rows import in seconds instead of minutes).

Source: backend/data/processed/mplads_normalized.csv (1,000 rows, real MoSPI/SBI
MPLADS records — see docs/MERGE-NOTES.md for full provenance). Only 3 of these
1,000 rows have a government-verified GPS coordinate; the rest are imported
honestly as evidence_source="unavailable" — real registry entries awaiting
either a future geolocation or a contractor's manually-uploaded evidence.

Additionally seeds 4 real legacy projects with manually-photographed
before/after evidence (backend/app/manual_evidence/) — 3 of these are among
the 1,000 CSV rows (and DO have a real coordinate, used only for map
placement) and use the manually-supplied high-resolution photos rather than
a 10m Sentinel-2 pass, since that's what actually shows the change clearly for
small-scale works like these. The 4th (Tamil Nadu Udayarpalayam) isn't in the
MPLADS CSV — it's a standalone real-world example with no coordinate at all.

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
        print(f"Importing {len(rows)} real MPLADS records from {CSV_PATH.name}...")

        manual_evidence_projects = []  # (Project, slug) pairs to analyze at the end
        geocoded_count = 0

        for i, row in enumerate(rows, start=1):
            lat, lon = _parse_float(row.get("latitude")), _parse_float(row.get("longitude"))
            has_coords = lat is not None and lon is not None
            work_id = row.get("work_id")

            project = Project(
                name=row["name"][:250],
                project_type=row.get("project_type") or "Public Works",
                description=(row.get("description") or "")[:1000],
                latitude=lat,
                longitude=lon,
                geometry_wkt=f"POINT({lon} {lat})" if has_coords else None,
                start_date=_parse_date(row.get("start_date")),
                expected_end_date=_parse_date(row.get("expected_end_date")),
                approved_cost=_parse_float(row.get("sanctioned_amount")),
                reported_progress=_parse_float(row.get("reported_progress")) or 0.0,
                status="normal",
                is_demo=0,
                evidence_source="satellite" if has_coords else "unavailable",
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

            if has_coords:
                geocoded_count += 1
            if work_id in MANUAL_EVIDENCE_FOR_CSV_ROWS:
                manual_evidence_projects.append((project, MANUAL_EVIDENCE_FOR_CSV_ROWS[work_id]))

            if i % 200 == 0:
                db.commit()
                print(f"  ...{i}/{len(rows)} imported")

        db.commit()
        print(f"Imported {len(rows)} real MPLADS records ({geocoded_count} with a verified GPS coordinate).")

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
