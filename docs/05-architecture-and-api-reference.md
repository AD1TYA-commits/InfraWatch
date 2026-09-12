# Architecture & API Reference

Technical reference for developers extending or integrating with this
system. For concepts explained from zero, see
[01-project-overview.md](01-project-overview.md); for setup steps, see
[03-developer-setup.md](03-developer-setup.md).

## System diagram

```
┌─────────────────┐      HTTP       ┌──────────────────────┐
│  Next.js         │ ───────────────▶│  InfraWatch backend   │
│  frontend        │◀─────────────── │  (FastAPI)            │
│  (port 3000)      │                │  (port 8000)           │
└─────────────────┘                └──────────┬───────────┘
                                               │ HTTP (real mode only)
                                               ▼
                                    ┌──────────────────────┐
                                    │  satellite-service     │
                                    │  (FastAPI, port 8001)   │
                                    │  sibling repo/folder    │
                                    └──────────┬───────────┘
                                               │ HTTPS
                              ┌────────────────┼────────────────┐
                              ▼                                 ▼
                   Microsoft Planetary Computer         Gemini API (optional)
                   (Sentinel-2 STAC + bands)             (narration only)
```

The InfraWatch backend persists to SQLite (local dev) or PostgreSQL+PostGIS
(Docker/production); satellite-service is stateless aside from a local
imagery cache on disk (`satellite-service/data/`).

## Request flow for "analyze a project"

1. Frontend calls `POST /api/projects/{id}/analyze`.
2. `execute_pipeline()` in `backend/app/api/projects.py` checks
   `SATELLITE_MODE` and whether bundled demo assets exist for this project
   id:
   - **Demo path**: loads bundled PNGs, runs the legacy in-process OpenCV
     `ChangeDetector` + `SatelliteChangeAnalyzer` (Gemini or fallback), builds
     the response directly.
   - **Real path**: calls `_execute_via_satellite_service()`, which POSTs to
     satellite-service's `/pipeline/run` with the project's lat/lon/name/
     reported progress, then maps that JSON response onto InfraWatch's own
     `AnalysisResultOut` schema and DB rows (`SatelliteObservation`,
     `AIResult`, `Anomaly`).
3. Either path writes fresh `SatelliteObservation`/`AIResult`/`Anomaly` rows
   and updates the project's `status`, then returns `AnalysisResultOut`.
4. The frontend renders the response directly — before/after images (URLs
   already absolute if from satellite-service, backend-relative if a
   bundled demo asset — see `resolveAssetUrl()` in `frontend/lib/api.ts`),
   the AI summary/changes, the recommendation banner, and the GeoJSON
   overlay on the map.

## InfraWatch backend API

Base URL: `http://localhost:8000`

| Method | Path | Purpose | Response shape |
|---|---|---|---|
| GET | `/api/health` | Liveness + DB connectivity | `HealthOut` |
| GET | `/api/projects` | Dashboard project list (includes `latest_image_url`) | `List[ProjectSummary]` |
| POST | `/api/projects` | Create a new project (`ProjectCreateIn`: name, project_type, latitude, longitude, reported_progress, etc.) | `ProjectOut` |
| GET | `/api/projects/kpi-summary` | Dashboard status counts | `KPISummary` |
| GET | `/api/projects/{id}` | Full project detail (milestones, financials, satellite observations, AI results, anomalies) | `ProjectOut` |
| POST | `/api/projects/{id}/analyze` | Run (or re-run) the satellite analysis pipeline for one project | `AnalysisResultOut` |
| POST | `/api/projects/{id}/ingest` | Force a fresh real-imagery fetch (used by the "Fetch Latest Sentinel-2" button) | `IngestResultOut` |
| GET | `/api/projects/{id}/evidence` | Latest stored screening evidence (auto-triggers analysis if none exists yet) | `EvidenceOut` |

All response shapes are defined in `backend/app/schemas/schemas.py` — that
file is the authoritative contract; this table is a map to it, not a
replacement for reading it when you need exact field types.

Interactive docs (Swagger UI, generated from the same schemas): visit
`http://localhost:8000/docs` while the backend is running.

## satellite-service API

Base URL: `http://localhost:8001` (see satellite-service's own README and
`docs/` for full detail — summarized here for convenience):

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness |
| POST | `/sentinel/fetch` | Fetch real Sentinel-2 imagery for one AOI |
| POST | `/model/detect?project_id=<key>` | Run change detection on a previously-fetched pair |
| POST | `/explain` | Narrate a given set of candidates (Gemini or template) |
| **POST** | **`/pipeline/run`** | **Fetch + detect + explain in one call — what InfraWatch's backend actually calls** |
| POST | `/pipeline/csv` | Same, batched over an uploaded CSV of projects |

## Database schema (InfraWatch)

Defined in `backend/app/models/models.py` (ORM) and
`backend/app/db/schema.sql` (canonical PostgreSQL+PostGIS DDL):

```
projects
├── milestones            (1:N, cascade delete)
├── financial_records      (1:N, cascade delete)
├── progress_reports        (1:N, cascade delete)
├── satellite_observations  (1:N, cascade delete) — one row per T1/T2 scene used
├── ai_results               (1:N, cascade delete) — one row per analysis run
└── anomalies                 (1:N, cascade delete) — the flagged discrepancy + explanation

audit_logs (project_id nullable FK, freestanding action log)
```

`satellite_observations.image_reference` holds either a bundled demo asset's
filename (served at `/demo-assets/<filename>` by this backend) or a
satellite-service-relative path like `data/T2/<id>/true_color.png` (resolved
to a full URL via `satellite_service_client.asset_url()`). The
`_latest_image_url()` helper in `api/projects.py` picks the right prefix
based on which shape the reference has.

## Key design decisions (the "why", not just the "what")

- **Two services, not one** — lets the ML/satellite piece be redeployed,
  retested, or replaced independently; see
  [01-project-overview.md](01-project-overview.md) §4.
- **A pretrained CNN feature-diff model, not raw pixel differencing or a
  vision LLM** — deterministic and reproducible (verified by an explicit
  test), doesn't need any training data, and keeps the one non-deterministic
  component (Gemini) out of the actual detection decision. Full rationale in
  satellite-service's `docs/01-concepts.md` §5.
- **Real Sentinel-2 bands, not the STAC `visual`/preview asset** — the
  preview is a compressed low-resolution JPEG meant for quick browsing; real
  analysis needs the actual 10m band data. This was the root cause of "only
  a few [projects] work" in the original prototype.
- **Demo mode kept as a separate, fully offline code path** — so the app is
  always demoable with zero setup and no internet dependency, even while
  `real` mode is being developed or when Planetary Computer/Gemini are
  unreachable.
