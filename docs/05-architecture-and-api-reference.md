# Architecture & API Reference

## System diagram

```text
┌─────────────────┐     JWT bearer      ┌──────────────────────────┐     HTTP      ┌───────────────────────┐
│  Next.js         │ ───────────────►   │  InfraWatch FastAPI       │ ───────────►  │  satellite-service     │
│  frontend        │ ◄─────────────── │  backend                 │ ◄─────────── │  (sibling microservice)│
│  (port 3000)     │     JSON           │  (port 8000)              │   JSON        │  (port 8001)           │
└─────────────────┘                    └──────────┬───────────────┘               └───────────┬────────────┘
                                                    │                                            │
                                          SQLAlchemy ORM                              rasterio + pretrained
                                                    │                                  ResNet18 feature-diff
                                          ┌─────────▼──────────┐                       + Gemini/template
                                          │ SQLite (dev) /       │                       narration
                                          │ PostgreSQL+PostGIS   │
                                          │ (users, projects,    │
                                          │ milestones, financial│
                                          │ records, satellite   │
                                          │ observations, AI     │
                                          │ results, anomalies)  │
                                          └──────────────────────┘
```

The backend never queries Sentinel-2 or runs the CNN model itself for a
real (non-demo) project — it delegates that entirely to satellite-service
over HTTP (`app/satellite_service_client.py`, `app/manual_evidence_client.py`)
and stores only the returned facts. There is no shared code or database
between the two services.

## Request flow for "analyze a project"

`POST /api/projects/{id}/analyze` → `execute_pipeline()` in
`app/api/projects.py` branches on the project's state:

1. **Bundled `[DEMO]` image pair exists and `SATELLITE_MODE != "real"`** →
   runs the legacy in-process pipeline (`satellite_provider.py` →
   `change_detector.py` → `change_crops.py` → `change_analyzer.py` →
   `geo_processor.py`), all local, no external calls.
2. **`evidence_source == "manual_upload"`** → `_execute_via_manual_evidence()`
   re-runs detection on the two most recently uploaded photos via
   satellite-service's `/model/detect-images` (see
   `app/manual_evidence_client.py`) — the same real model as the satellite
   path, applied to manually-sourced images instead of a georeferenced pass.
3. **Has a real lat/lon** → `_execute_via_satellite_service()` calls
   satellite-service's `/pipeline/run` (see `app/satellite_service_client.py`)
   — real Sentinel-2 fetch, real model, real narration.
4. **Neither a coordinate nor manual evidence** → `_unavailable_result()`
   records an honest `watch`-severity "evidence unavailable" anomaly. This
   is the common, expected state for most bulk-imported real MPLADS rows,
   not an error.

In every branch, the resulting `observed_change` percentage is compared
against the project's `reported_progress` to decide a recommendation
(`Field verification recommended` / `No significant discrepancy` /
`Review recommended`) and severity, and is available afterward to the risk
engine via the most recent `AIResult` row.

## InfraWatch backend API

All endpoints are prefixed as shown; auth is a `Bearer <JWT>` header where
required.

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/health` | none | API + database connectivity check |
| POST | `/api/auth/register` | none | Create an account; returns a token immediately |
| POST | `/api/auth/login` | none | Exchange email/password for a token |
| GET | `/api/auth/me` | any authenticated user | Current user's profile |
| GET | `/api/projects` | any authenticated user | Paginated registry (`page`, `page_size` ≤ 500, `data_source`, `evidence_source` filters) |
| GET | `/api/projects/mine` | contractor | The calling contractor's own projects |
| POST | `/api/projects` | contractor | Register a new project — `latitude`/`longitude` required |
| GET | `/api/projects/kpi-summary` | any authenticated user | Status counts over the entire registry |
| GET | `/api/projects/{id}` | any authenticated user | Full project detail, including milestones/financial records/observations/AI results/anomalies |
| GET | `/api/projects/{id}/evidence` | any authenticated user | Latest screening evidence summary (auto-triggers analysis if none exists yet) |
| POST | `/api/projects/{id}/evidence/upload` | contractor | Upload before/after photos (multipart) for a no-coordinate project; runs detection immediately |
| GET | `/api/projects/{id}/risk` | any authenticated user | Composite risk score + 4-factor breakdown + duplicate-candidate list |
| POST | `/api/projects/{id}/analyze` | any authenticated user | Run (or re-run) the appropriate evidence pipeline |
| POST | `/api/projects/{id}/ingest` | any authenticated user | Force a fresh imagery/evidence fetch, then analyze |

Static file mounts: `/demo-assets/*` (bundled demo image pairs) and
`/manual-evidence/*` (contractor-uploaded and seeded real evidence photos) —
these are unauthenticated, since they only ever serve non-sensitive image
files whose paths are opaque IDs, not the registry data itself.

Every `/api/projects...` route requires being logged in as *some* account
(analyst or contractor) — there is no anonymous read access to the registry,
matching the "proper login for security" requirement. Only three routes are
further restricted to the contractor role specifically: creating a project,
uploading manual evidence, and `/mine`.

## satellite-service API

Full contract in `satellite-service/docs/04-integration.md` and its own
README; summarized here for convenience.

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness check |
| POST | `/sentinel/fetch` | Fetch real Sentinel-2 T1/T2 imagery for an AOI |
| POST | `/model/detect?project_id=` | Run PlanAura detection on a previously-fetched pair |
| POST | `/model/detect-images` | Run PlanAura detection directly on two **uploaded** images (no STAC fetch) — used for manual evidence |
| POST | `/explain` | Gemini/template narration of a set of already-computed candidates |
| POST | `/pipeline/run` | Fetch + detect + explain in one call — what InfraWatch calls per project |
| POST | `/pipeline/csv` | Same, batched over an uploaded CSV of projects |

`/pipeline/run`'s response includes `observable_change_percent`,
`candidate_count`, a GeoJSON `FeatureCollection` overlay, before/after/mask
image paths (served as static files at satellite-service's own host, e.g.
`http://localhost:8001/data/T2/42/true_color.png`), a structured
`explanation` block, and a `model_version` string
(`planaura-resnet18-featurediff-v1`). A failed fetch (no cloud-free scene,
AOI outside coverage) still returns HTTP 200 with `error` set to a
human-readable reason, rather than an HTTP error — InfraWatch's
`_unavailable_result()` handles this path explicitly rather than treating it
as a crash.

## Data model summary

Core tables (`backend/app/models/models.py`):

- **`User`** — `email`, `hashed_password` (bcrypt), `role`
  (`"analyst"`/`"contractor"`), `full_name`, `organization`.
- **`Project`** — `name`, `project_type`, `description`, `latitude`/
  `longitude` (**nullable on purpose** — see below), `geometry_wkt`,
  `start_date`/`expected_end_date`, `approved_cost`, `reported_progress`,
  `status`, `is_demo`, `evidence_source`
  (`"satellite"` / `"manual_upload"` / `"unavailable"`), real-government
  metadata (`work_id`, `mp_name`, `state_name`, `constituency_name`,
  `district_name`, `implementing_agency`, `sanctioned_amount`,
  `actual_expenditure`, `data_source`), and `owner_user_id` (which
  contractor account registered/owns it, if any).
- **`Milestone`**, **`FinancialRecord`**, **`ProgressReport`** — schedule and
  disbursement history.
- **`SatelliteObservation`** — one row per before/after image
  (`source` is `"demo"`, `"sentinel-2-l2a (satellite-service)"`,
  `"manual-upload"`, etc.; `image_reference` is a path/asset id, never a raw
  raster stored in the DB).
- **`AIResult`** — the model's output for one observation pair (`changed_area`,
  `observed_progress`, `confidence`, `model_version`).
- **`Anomaly`** — one flagged signal (`type`, `score`, `severity`,
  `explanation`).
- **`AuditLog`** — free-text action log (`user_action`, `project_id`,
  timestamp).

`latitude`/`longitude` are nullable deliberately: real bulk-imported
government records (like MPLADS) very often have no published GPS
coordinate. Such a project is still real and legitimate data — it simply
can't be satellite-screened until either a coordinate becomes available or
a contractor supplies manual evidence (`evidence_source`).

The canonical Postgres schema (`app/db/schema.sql`) defines `geometry` as a
real PostGIS `GEOMETRY(Point, 4326)` column with a GIST index for
production; the ORM layer stores geometry as WKT text (`geometry_wkt`) so
the exact same model code runs unchanged against SQLite for local dev.

## The manual-evidence design decision

A project with no GPS coordinate cannot be satellite-screened — but it
still needs *some* honest way to be evaluated once photographic evidence
exists. Rather than inventing a second, weaker change-detection path for
this case, InfraWatch reuses satellite-service's exact same PlanAura model
via a second endpoint (`/model/detect-images`) that accepts two uploaded
images directly instead of fetching them from Sentinel-2. The resulting
`observable_change_percent` is real model output — not a placeholder or a
fabricated number — even though the source photos aren't a georeferenced
satellite pass. The risk engine's `evidence_type` field
(`"real_satellite"` / `"manual_upload"` / `"legacy_demo"` / `"unavailable"`)
tracks this distinction and caps confidence accordingly (manual-upload
evidence never claims satellite-grade confidence — see below).

## Risk engine: formula and weights

`app/risk_engine.py`'s `evaluate_project_risk()` combines four independent,
deterministic components into one 0-100 composite score
(`app/config.py`'s `RISK_WEIGHTS`):

| Component | Weight | What it measures |
|---|---|---|
| Satellite discrepancy | 50% | `abs(reported_progress - observed_change)`, scaled non-linearly; over-reporting is penalized more than under-reporting (an unexplained large gap where reported > observed is the most actionable signal) |
| Financial overrun | 20% | `(actual_expenditure - sanctioned_amount) / sanctioned_amount`, with tiered scaling above a 5% allowable variance |
| Timeline / delay | 15% | Days past `expected_end_date`, plus a stalling check (started >1 year ago, <5% reported progress) |
| Duplicate work | 15% | Text (Jaccard token similarity) + amount + category + geographic proximity similarity to other works in the same district |

```
risk_score = 0.50 * satellite_score + 0.20 * financial_score
           + 0.15 * timeline_score  + 0.15 * duplicate_score
```

Classification (`_classify()`): **LOW** ≤ 24, **MEDIUM** ≤ 49, **HIGH** ≤ 74,
**CRITICAL** > 74.

Each component individually returns `has_data: false` (not a fabricated
score) when its required inputs are missing — missing data lowers
confidence, it is never treated as risk. The composite `confidence` field is
an average of each component's own confidence, additionally capped at 0.45
whenever the evidence isn't from a real satellite pass (manual-upload or
demo evidence never claims satellite-grade certainty).

**No project ID is ever accepted by, or special-cased in, any risk-engine
function** — `compute_satellite_discrepancy_risk()` doesn't even take a
`project_id` parameter, which a dedicated test enforces via
`inspect.signature`. See [MERGE-NOTES.md](MERGE-NOTES.md) for why this
matters.

## Key design decisions (the "why", not just the "what")

- **satellite-service is a separate repo/microservice, not a module inside
  `backend/`** — so it can be redeployed, restarted, or replaced
  independently, and so its lack of its own auth (by design, meant to sit
  behind the main backend) is contained to an internal network boundary.
- **Coordinates are mandatory for new contractor-registered projects, but
  nullable for imported records** — new data should never be created in an
  unscreenable state; legacy/bulk-imported data often arrives that way and
  should be represented honestly rather than dropped or faked.
- **Manual evidence reuses the real model, not a second bespoke one** — a
  contractor's uploaded photos get a real, comparable model score instead of
  a lower-fidelity heuristic that would be harder to reason about
  consistently against satellite-screened projects.
- **The risk engine takes no project identifiers at all in its component
  functions** — this is a structural guarantee against per-project
  hardcoding, not just a coding convention; see
  [MERGE-NOTES.md](MERGE-NOTES.md) for the history behind this decision.
- **Auto-seeding only ever runs against a genuinely empty database**
  (`app/main.py` checks `Project` count before seeding) — a container
  restart or a `docker compose up` against an existing volume can never
  silently wipe or duplicate real imported data.
