# Testing & QA

What's automatically tested, what isn't, and the manual checklist to run
through before any demo or handoff. Keep this updated as coverage changes —
a stale testing doc is worse than none.

## Automated tests

### InfraWatch backend (`backend/tests/`, pytest)

```bash
cd backend && pytest tests/ -v
```

| File | Covers |
|---|---|
| `test_api.py` | Health check, project list/detail, Esri fallback provider, OpenCV change detector + GeoJSON conversion, Gemini-analyzer fallback, the full demo-mode `/analyze` workflow |
| `test_satellite_service_integration.py` | The satellite-service HTTP client (success + transport-failure paths, mocked — no network needed), the adapter that turns satellite-service's JSON into InfraWatch's DB rows/schema (including a regression test for the datetime-string bug caught during real integration testing), graceful degradation when satellite-service is unreachable, and `latest_image_url` resolution for both demo-asset and satellite-service image paths |

12 tests total, all mocked/offline — no internet or a running satellite-service
required to run this suite.

### satellite-service (`satellite-service/tests/`, pytest)

```bash
cd ../satellite-service && pytest tests/ -v
```

4 tests, using synthetic images (no network needed): the PlanAura model is
deterministic (identical input → byte-identical output), it detects an
introduced synthetic change region, it reports zero change for identical
images, and candidate-to-GeoJSON vectorization produces valid polygons.

### What's *not* covered by automated tests

- **The frontend has no automated test suite** (no Jest/Playwright/etc. set
  up). Every frontend check below is manual. If this project continues past
  the hackathon, this is the highest-value gap to close next — starting
  with a smoke test for the dashboard load + project detail analyze flow.
- **Live network integration** (real Planetary Computer STAC calls, real
  Gemini calls) is exercised by manual testing only, documented below and in
  satellite-service's own docs. Automated tests deliberately mock these to
  stay fast and not depend on external services being up.
- **No labeled ground-truth validation** — nothing confirms the model's
  change-detection thresholds actually match real construction outcomes;
  see the limitations section in
  [01-project-overview.md](01-project-overview.md).

## Manual QA checklist

Run through this after any change to the frontend, the satellite pipeline,
or before a demo. Needs all three services running (see
[03-developer-setup.md](03-developer-setup.md)).

**Dashboard**
- [ ] Loads without console errors, KPI cards show correct counts
- [ ] Map renders with one pin per project, correct color per priority
- [ ] Search box filters both the table and the map pin count
- [ ] Priority and sector filter pills work
- [ ] Clicking a map pin opens its popup with a real (not broken) thumbnail
- [ ] Dark/light theme toggle doesn't break any layout
- [ ] **Scroll the page and confirm the navbar always stays visually on top
      of the map** — this was a real bug (Leaflet's z-index escaping past
      the sticky header); re-check this specifically after any CSS/layout
      change near the map or header

**Project detail page**
- [ ] Opening a project auto-runs analysis; loading state shows, then
      resolves (don't confuse a slow real-mode fetch, 10-30s, with a hang)
- [ ] Before/after comparison slider renders, drags smoothly, and both
      corner labels show correct T1/T2 dates
- [ ] When candidates exist, highlighted boxes appear on the slider at the
      right positions on both images, and hovering one shows a tooltip with
      type/confidence/area (test with `CHANGE_MIN_CONFIDENCE` lowered on
      satellite-service if the current data has zero candidates — see
      `satellite-service/.env.example`)
- [ ] AI summary, confidence, and recommendation banner are consistent with
      each other (e.g., "no significant change" shouldn't pair with a
      "construction detected" category)
- [ ] Map at the bottom shows the same location with change-region overlay,
      toggleable on/off
- [ ] Milestones and Financials tabs render their data correctly
- [ ] "Run Analysis Again" re-triggers without error
- [ ] "Export Report (PDF)" downloads a PDF with project info, both
      satellite images, the AI summary/recommendation, and the change-region
      table; verify it still downloads something sensible (with a note
      instead of images) if image fetching fails

**Backend**
- [ ] `GET /api/health` returns `200` with `database: connected`
- [ ] `POST /api/projects/{id}/analyze` succeeds for both a demo-mode and
      (if `SATELLITE_MODE=real`) a real-mode project
- [ ] A deliberately bad location (e.g., open ocean coordinates) degrades
      gracefully — returns a clear explanation, not a 500 or a crash

**satellite-service**
- [ ] `GET /health` returns `200`
- [ ] `/pipeline/run` against a real land coordinate returns real Sentinel-2
      dates (not placeholder/epoch dates)
- [ ] `/pipeline/csv` correctly processes a multi-row CSV and isolates a bad
      row's error without failing the whole batch

## Known issues log

Keep this current — remove an item once actually fixed, add new ones as
found. As of this writing:

- No authentication on either service (expected for local/prototype use;
  flagged again here so it isn't missed before any real deployment).
- Change-detection thresholds are hand-tuned, not validated against labeled
  data.
- No automated frontend tests (see above).
