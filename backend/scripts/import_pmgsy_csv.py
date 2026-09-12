"""
Imports real-world project locations from a PMGSY-derived CSV
(see ../../satellite-service/samples/pmgsy_real_projects.csv) into InfraWatch
via its real HTTP API — the same POST /api/projects + POST /analyze path the
actual product uses, not a side-channel DB script.

Usage:
    python -m scripts.import_pmgsy_csv [path/to.csv] [--base-url http://localhost:8000]

CSV columns expected: name, latitude, longitude, project_type, reported_progress
(project_id/district/state/source_category columns, if present, are ignored —
InfraWatch assigns its own project IDs).

Each row's name is prefixed with "[PMGSY-REAL]" so it's unmistakable in the UI
that this is real-location data with a synthetic reported_progress placeholder
(PMGSY facility data has no real "self-reported construction progress" — these
are existing operational facilities, not in-progress works).
"""
import csv
import sys
import time
import argparse
from pathlib import Path

import httpx

DEFAULT_CSV = Path(__file__).resolve().parents[3] / "satellite-service" / "samples" / "pmgsy_real_projects.csv"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("csv_path", nargs="?", default=str(DEFAULT_CSV))
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument("--skip-analyze", action="store_true", help="Only create projects, don't run analysis yet")
    args = parser.parse_args()

    csv_path = Path(args.csv_path)
    if not csv_path.exists():
        print(f"CSV not found: {csv_path}")
        sys.exit(1)

    with open(csv_path, newline="") as f:
        rows = list(csv.DictReader(f))

    print(f"Importing {len(rows)} real project locations from {csv_path.name}...")

    created = []
    for i, row in enumerate(rows, start=1):
        payload = {
            "name": f"[PMGSY-REAL] {row['name']}",
            "project_type": row["project_type"],
            "description": (
                "Real facility location sourced from PMGSY open data (OMMAS, "
                "via Government of India Open Data License). Reported progress "
                "below is a synthetic placeholder for demo purposes only — "
                "this facility already exists; it is not an in-progress "
                "construction work with a real self-reported completion claim."
            ),
            "latitude": float(row["latitude"]),
            "longitude": float(row["longitude"]),
            "reported_progress": float(row["reported_progress"]),
        }
        resp = httpx.post(f"{args.base_url}/api/projects", json=payload, timeout=30.0)
        resp.raise_for_status()
        project = resp.json()
        created.append(project)
        print(f"  [{i}/{len(rows)}] Created #{project['id']}: {project['name']}")

    if args.skip_analyze:
        print("\nSkipped analysis (--skip-analyze). Projects will analyze on first dashboard view.")
        return

    print(f"\nRunning real satellite analysis for {len(created)} projects (this calls satellite-service for each — expect ~10-20s per project)...")
    for i, project in enumerate(created, start=1):
        start = time.time()
        try:
            resp = httpx.post(f"{args.base_url}/api/projects/{project['id']}/analyze", timeout=120.0)
            resp.raise_for_status()
            result = resp.json()
            duration = round(time.time() - start, 1)
            print(
                f"  [{i}/{len(created)}] #{project['id']} {project['name'][:50]}: "
                f"{result['observable_change_percent']}% change, "
                f"{result['candidate_count']} regions, {duration}s"
            )
        except Exception as exc:
            print(f"  [{i}/{len(created)}] #{project['id']} FAILED: {exc}")

    print("\nDone. Open http://localhost:3000 to see them on the dashboard.")


if __name__ == "__main__":
    main()
