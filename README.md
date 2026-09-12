# InfraWatch

AI-assisted decision-support prototype for **SIH26102: AI-powered detection of
anomalies, fraud and inefficiencies in MPLADS implementation**.

> **What this system does and does not claim.** InfraWatch flags
> discrepancies between *reported* progress and satellite-*observed* change,
> and recommends field verification. It never states that fraud is
> confirmed, that a contractor is guilty, or that a worker has committed a
> crime, and it never files anything automatically. Every output is a
> recommendation for a human government official to review.

## 1. Project status and roadmap

The current prototype includes the project dashboard, map, API, demo data,
satellite-image comparison workflow, and evidence summaries. It is a
decision-support tool; its outputs require human review.

| Area | Status |
|---|---|
| Dashboard, map, project details, API and demo data | Available |
| Satellite-image comparison and evidence summaries | Available for the demo workflow |
| Login and account management | Planned |
| Role-based access control (for example, administrator and field officer roles) | Planned |
| Login security layers, including secure sessions, password protection, authorization checks and audit logging | Planned before production use |
| Validated AI model training, evaluation and deployment | Planned; current results are screening support only |

## 2. Architecture

```
PostgreSQL + PostGIS  →  FastAPI  →  Next.js  →  Dashboard / Map / Detail UI
                                          ↑
                         (Phase 2+) Satellite imagery → preprocessing →
                         change detection → progress estimate → risk engine
```

Satellite ingestion, image processing, and the anomaly engine are kept as
separate backend modules (`app/services/`, to be added in Phase 2) so they
can be swapped or extended — e.g. demo imagery → real Sentinel-2 — without
touching the database schema or API contracts.

## 3. Tech stack

- **Frontend:** Next.js 14 (App Router), TypeScript, Tailwind CSS, Leaflet (via react-leaflet)
- **Backend:** Python, FastAPI, Pydantic
- **Database:** PostgreSQL + PostGIS (production/Docker); SQLite (zero-setup local dev — see note below)
- **Geospatial/ML (wired in for Phase 2+):** GeoPandas, Shapely, Rasterio, NumPy, OpenCV
- **Dev tooling:** Git, Docker, pytest

### A note on the database in Phase 1

The canonical schema is PostGIS-native — see `backend/app/db/schema.sql`,
which `docker-compose` applies automatically to a real PostGIS-enabled
Postgres container. For local development *without* Docker, the same
SQLAlchemy models create an equivalent SQLite schema (`latitude`/`longitude`
are always plain floats per spec; the `geometry` column is stored as WKT
text in SQLite mode rather than a true PostGIS geometry type, since SQLite
has no PostGIS). Nothing else about the app changes between the two modes.
Point this at a real Postgres+PostGIS instance any time by setting
`DATABASE_URL`.

## 4. Installation & running locally

### Option A — without Docker

**Backend:**
```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m scripts.seed_demo_data
uvicorn app.main:app --reload --port 8000
```
API docs (OpenAPI/Swagger) are then at `http://localhost:8000/docs`.

**Frontend** (separate terminal):
```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```
Dashboard at `http://localhost:3000`.

### Option B — with Docker

```bash
docker-compose up --build
```
This starts a real PostgreSQL+PostGIS database, seeds it, runs the backend
on `:8000` and the frontend on `:3000`.

## 5. Environment variables

**Backend** (`backend/.env`, see `backend/.env.example`):
| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | DB connection string | `sqlite:///./infrawatch.db` |
| `SATELLITE_MODE` | `demo` or `real` | `demo` |
| `COPERNICUS_CLIENT_ID` / `COPERNICUS_CLIENT_SECRET` | Sentinel-2 credentials, only needed in `real` mode | empty |

**Frontend** (`frontend/.env.local`, see `frontend/.env.example`):
| Variable | Purpose | Default |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Backend URL the frontend calls | `http://localhost:8000` |

No credentials are hard-coded anywhere in the codebase.

## 6. Demo mode vs. real Sentinel-2 mode

- **Demo mode** (default): the app runs fully offline using six clearly
  labeled `[DEMO]` synthetic projects (`backend/scripts/seed_demo_data.py`).
  No external APIs or credentials required. Demo imagery and demo change
  detection arrive in Phase 2 — labeled `DEMO DATA` throughout the UI.
- **Real mode** (Phase 3): a Sentinel-2 adapter against the Copernicus Data
  Space Ecosystem, gated behind `SATELLITE_MODE=real` and the Copernicus
  credentials above. Not yet implemented in this Phase 1 slice.

## 7. Database setup

Eight tables per the spec: `projects`, `milestones`, `financial_records`,
`progress_reports`, `satellite_observations`, `ai_results`, `anomalies`,
`audit_logs`. Canonical DDL: `backend/app/db/schema.sql`. Large raster files
are never stored in the database — only references/paths, per
`satellite_observations.image_reference`.

## 8. API endpoints (Phase 1)

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | Liveness + DB connectivity check |
| GET | `/api/projects` | List all projects (map/dashboard view) |
| GET | `/api/projects/{id}` | Full detail for one project |
| GET | `/api/projects/kpi-summary` | Counts by risk status for KPI cards |

Full interactive docs at `/docs` (Swagger UI) once the backend is running.
| POST | `/api/projects/{id}/ingest` | Discover, download and prepare two Sentinel-2 L2A scenes in `SATELLITE_MODE=real`; returns local demo scenes otherwise |
| POST | `/api/projects/{id}/analyze` | Create transparent before/after observable-change screening result |
| GET | `/api/projects/{id}/evidence` | Return the latest decision-support evidence summary |

## 9. Change detection methodology (planned, Phase 2)

The MVP will use a **transparent baseline**, not an opaque deep-learning
model: normalized pixel/band difference between two co-registered,
cloud-filtered images, thresholded and cleaned with morphological noise
removal. The output is explicitly called **Observable Change**, not
"construction progress" — vegetation, shadows, clouds, and seasonal effects
can all produce false positives, and the system will say so. A learned model
is only introduced later, once labeled construction-stage data exists to
validate it against.

## 10. Limitations (current, Phase 1)

- No satellite imagery, change detection, or anomaly/risk scoring yet — those are Phase 2.
- SQLite dev mode does not exercise real PostGIS geometry queries (spatial indexing, `ST_*` functions); only Docker/Postgres mode does.
- All data currently in the system is synthetic demo data, clearly labeled.
- No auth/access-control layer yet (out of scope for this MVP slice).
- Frontend detail-page data is client-side fetched (not server-rendered) for simplicity in Phase 1.

## 11. Future development

The Docker setup defaults to real imagery. In this mode, the app queries the
public Microsoft Planetary Computer STAC API for real Sentinel-2 L2A scenes,
downloads two cloud-filtered true-colour previews, and compares them locally.
No account is required for normal project-sized queries. Set
`SATELLITE_MODE=demo` only when a fully offline workflow is needed. The
resulting pixel change is screening evidence, not a construction-progress or
fraud finding.

## 12. Testing

```bash
cd backend
pytest tests/ -v
```
Covers: health check, project listing, project detail, 404 handling for an
unknown project, and KPI aggregation. All 5 tests pass as of this Phase 1
delivery (verified against a live, running server — not just the test
client — during development).
