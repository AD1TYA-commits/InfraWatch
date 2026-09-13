# Testing & QA

## Automated tests

### InfraWatch backend (`backend/tests/`, pytest)

23 tests across three files. Run with:

```bash
cd backend
pytest tests/ -v
```

**`test_auth_and_risk.py` (12 tests)** — authentication and the risk engine:

- Registration + login + `/api/auth/me` round trip.
- Wrong password is rejected (401); duplicate email registration is
  rejected (409).
- Password is actually hashed (bcrypt, `$2b$` prefix), never stored plain.
- Project creation requires the `contractor` role (403 for an analyst) and
  requires authentication at all (401 with no token).
- `compute_cost_overrun_risk` scales with overrun size and returns
  `has_data=False` (not a fabricated risk) when financial figures are
  missing.
- `compute_timeline_risk` flags delay correctly and marks `is_delayed`.
- **`compute_satellite_discrepancy_risk` takes no `project_id` parameter at
  all** — asserted via `inspect.signature` — so it cannot be special-cased
  per project even in principle. This directly guards against the pattern
  the earlier New1 branch used (`check_manual_project`/
  `check_small_scale_exception`, hardcoded per-ID overrides); see
  [MERGE-NOTES.md](MERGE-NOTES.md).
- The composite score never exceeds 100 regardless of how extreme the
  inputs are, and an arbitrary/unseen `project_id` produces the same
  CRITICAL result a real one with identical inputs would (proving there's no
  ID-keyed special-casing anywhere in the composite path either).
- `GET /api/projects/{id}/risk` returns all 4 weighted factors with scores,
  weights, and explanations.
- **Real-satellite evidence isn't wrongly confidence-capped** — regression
  test for a bug where the confidence-capping check compared against a
  value (`"real_satellite"`) that `Project.evidence_source` never actually
  set (it's always `"satellite"`), so every risk assessment — even genuinely
  real Sentinel-2-screened ones — silently had its confidence capped at 0.45
  with a self-contradictory "not a real satellite pass" explanation.

**`test_api.py` (6 tests)** — core project API, exercised against the real
pipeline with satellite-service's HTTP call mocked:

- Health check reports `database: connected`.
- `GET /api/projects` with no token is rejected (401) — the registry has no
  anonymous read access.
- Project list/detail endpoints return the expected shape and fields (once
  authenticated).
- The full `/analyze` workflow (mocking `satellite_service_run_pipeline`)
  returns scene metadata and a GeoJSON overlay.
- Contractor-authenticated project creation (`POST /api/projects`) succeeds
  and the new project immediately appears in the registry list.

**`test_satellite_service_integration.py` (5 tests)** — the HTTP integration
layer with the real satellite-service, all mocked (no network needed):

- `run_pipeline()`'s HTTP client succeeds against a well-formed response and
  wraps transport failures (`httpx.ConnectError`, etc.) in
  `SatelliteServiceError` rather than leaking the raw exception.
- `_execute_via_satellite_service` correctly parses satellite-service's
  ISO-string acquisition dates into real `datetime` objects before writing
  them to a SQLAlchemy `DateTime` column — a regression test for a real bug
  caught during end-to-end testing (SQLAlchemy rejects a raw ISO string).
- On a satellite-service failure, the project degrades gracefully to a
  `watch`-severity anomaly explaining why, instead of the request crashing.
- `list_projects()`'s `latest_image_url` field resolves correctly for both a
  manually-uploaded evidence photo (`/manual-evidence/...`) and a real
  satellite-service result (absolute URL at the satellite-service host).

### satellite-service (`satellite-service/tests/`, pytest)

Its own repository, its own test suite (`test_change_detection.py`) —
offline, synthetic-image-based tests of the change-detection model, run
from within `satellite-service/`:

```bash
cd ../satellite-service
pytest tests/ -v
```

Not re-tested from InfraWatch's side beyond the mocked integration-shape
tests above — see that repo's own `docs/` for details.

### Frontend

No automated test runner (Jest/Playwright/etc.) is configured. The
correctness check in place is a TypeScript compile:

```bash
cd frontend
npx tsc --noEmit
```

This catches type errors (wrong prop shapes, mismatched API response types
in `types/project.ts`, etc.) but not runtime/behavioral regressions.

### What's *not* covered by automated tests

- Any actual UI interaction (clicking through the dashboard, submitting the
  register-project or upload-evidence forms, the PDF export) — verified
  manually (see checklist below).
- Real Sentinel-2 fetches or a real Gemini API call (both need network
  access/credentials and are non-deterministic in the Gemini case; only the
  deterministic model and the HTTP integration shape are tested).
- Visual/design regressions in the redesigned light-navy/gold-serif theme.
- Load/concurrency behavior of the JWT auth layer under many simultaneous
  users.

## Manual QA checklist

Run through this after any change touching auth, the risk engine, or the
evidence-upload flow:

**Auth**
- [ ] Register a new analyst account; confirm redirect to `/`.
- [ ] Register a new contractor account; confirm redirect to `/contractor`.
- [ ] Log out, log back in with each; confirm the right dashboard loads.
- [ ] Attempt to open `/contractor` as an analyst (and `/` as a contractor);
      confirm the redirect in `useRequireAuth` sends you to the right place.
- [ ] Attempt `POST /api/projects` with an analyst's token via `/docs`;
      confirm 403.

**Analyst dashboard**
- [ ] KPI cards match `/api/projects/kpi-summary`, not just the loaded page.
- [ ] Search, priority filter, sector filter, registry-source filter, and
      evidence-type filter each narrow the table correctly and can be
      combined.
- [ ] Pagination's Next/Previous buttons work and disable at the boundaries.
- [ ] Map markers appear only for projects with a GPS coordinate.
- [ ] Every registry row shows the correct evidence-type badge (🛰️
      Satellite / 📷 Manual Upload / — Awaiting Evidence).

**Project detail**
- [ ] "Run Analysis Again" on a satellite-screened project produces a
      before/after slider, a recommendation banner, and an updated risk
      breakdown.
- [ ] A no-coordinate project with manual evidence shows the "no GPS —
      manually-supplied evidence" note instead of a map.
- [ ] "Export Report (PDF)" downloads a report containing the project name,
      risk score, and (where available) the before/after images.

**Contractor workflow**
- [ ] Register a new project without lat/lon; confirm the form blocks
      submission client-side with the mandatory-GPS message.
- [ ] Register a new project with valid lat/lon; confirm it appears under
      "My Projects" and is tagged evidence_source=satellite.
- [ ] Upload before/after evidence for a no-coordinate project; confirm the
      response shows a real observable-change percentage and region count
      (not a constant/placeholder value), and that re-uploading against a
      project that already has a coordinate is rejected with a clear error.

**Live satellite-service (needs internet)**
- [ ] `./start-all.sh`; confirm satellite-service's health check and a live
      `/pipeline/run` call both succeed for a real-coordinate project.

## Known issues log

- satellite-service's confidence thresholds are hand-tuned on manual checks,
  not validated against a labeled ground-truth dataset — treat all outputs
  (both here and in InfraWatch's risk engine) as screening signal.
- There is no offline/bundled-image fallback mode — satellite-service must
  be reachable, and internet access is required, for any coordinate-based
  project's analysis. An earlier iteration had a legacy in-process pipeline
  and 6 fully-synthetic `[DEMO]` projects for offline use; both were removed
  once real data covered the "something to show immediately" need — see
  [MERGE-NOTES.md](MERGE-NOTES.md).
