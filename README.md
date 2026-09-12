# InfraWatch

InfraWatch is an SIH26102 prototype for helping officials compare reported
MPLADS project progress with observable change between two images. It provides
screening evidence for human review; it does not make fraud or guilt findings.

**Want to just run it? Put this repo next to a `satellite-service` folder
(same parent directory) and run:**

```bash
./start-all.sh
```

That's the entire setup — no manual database, dataset, or config step.
First run takes a few minutes (installs everything); every run after that
takes seconds. See [docs/00-quickstart.md](docs/00-quickstart.md) if
anything about that isn't obvious.

**New to this project otherwise? Start in
[`docs/01-project-overview.md`](docs/01-project-overview.md)** instead of
this file. This README is a quick reference; the `docs/` folder has the
full walkthrough:

| Doc | For |
|---|---|
| [docs/00-quickstart.md](docs/00-quickstart.md) | The one command to run everything — start here |
| [docs/01-project-overview.md](docs/01-project-overview.md) | What this project is, the problem it solves, how it works end to end |
| [docs/02-user-guide.md](docs/02-user-guide.md) | Using the dashboard — for field officers, reviewers, demo audiences |
| [docs/03-developer-setup.md](docs/03-developer-setup.md) | Cloning, installing, running and building this from scratch |
| [docs/04-testing-and-qa.md](docs/04-testing-and-qa.md) | Automated test coverage + manual QA checklist |
| [docs/05-architecture-and-api-reference.md](docs/05-architecture-and-api-reference.md) | System diagram, full API reference, DB schema, design rationale |

## Current scope

The application includes a FastAPI backend, Next.js dashboard, project map,
SQLite/PostgreSQL database, bundled demo image pairs for offline demos, and a
standalone **satellite-service** microservice (sibling repo/folder) that
performs real Sentinel-2 fetch, pretrained-model change detection, and
Gemini/template narration. All seeded projects are demo records; imagery and
change detection are real once `SATELLITE_MODE=real` is set.

| Area | Status |
|---|---|
| Dashboard, map, project details, API and demo data | Available |
| Real Sentinel-2 imagery + pretrained-model change detection | Available via satellite-service (`SATELLITE_MODE=real`) |
| Image comparison, change mask and GeoJSON overlay | Available, both demo and real modes |
| Gemini analysis | Optional; requires `GEMINI_API_KEY` (falls back to a templated summary otherwise) |
| Login, user management and role-based access control | Planned |
| Secure sessions, password protection, authorization and audit controls | Planned before production use |
| Validated ML model evaluation against labeled ground truth | Planned |

## Architecture

```text
Next.js dashboard/map  ⇄  InfraWatch FastAPI backend  ⇄  satellite-service (separate microservice)
         ↑                          ↓                              ↓
   Leaflet map +           SQLite/PostgreSQL+PostGIS      Sentinel-2 fetch → pretrained
   GeoJSON overlay          (projects, milestones,         CNN change detection →
                             satellite observations,        Gemini/template narration
                             AI results, anomalies)
```

See [docs/05-architecture-and-api-reference.md](docs/05-architecture-and-api-reference.md)
for the full request-flow breakdown and API tables.

## Technology

- Frontend: Next.js, TypeScript, Tailwind CSS, Leaflet
- Backend: Python, FastAPI, SQLAlchemy, Pydantic
- Image processing: OpenCV, Rasterio, NumPy, GeoPandas, Shapely
- Database: PostgreSQL with PostGIS for deployment; SQLite for local demo

## Run locally

**Recommended — one command, everything automatic** (requires
`satellite-service` cloned as a sibling folder next to this repo):

```bash
./start-all.sh          # demo mode: bundled images, no internet needed
./start-all.sh real     # real mode: live Sentinel-2 imagery
```

First run installs everything and takes a few minutes; every run after that
takes seconds. The demo database and its 6 sample projects are created
automatically — nothing to prepare by hand. Press `Ctrl+C` to stop
everything cleanly. See [docs/00-quickstart.md](docs/00-quickstart.md) for
the full walkthrough and troubleshooting.

**Manual, piece by piece** (useful if you want to run just one service, or
understand what the script above does) — backend:

```bash
cd backend
./setup.sh   # or manually: python -m venv .venv && source .venv/bin/activate
             # && pip install -r requirements.txt && cp .env.example .env
./run.sh     # or: uvicorn app.main:app --reload --port 8000
```

Frontend, in a second terminal:

```bash
cd frontend
./setup.sh   # or: cp .env.example .env.local && npm install
./run.sh     # or: npm run dev
```

For real Sentinel-2 imagery (not just bundled demo images), also run
satellite-service (`./setup.sh && ./run.sh` in that repo too) and set
`SATELLITE_MODE=real` in `backend/.env`.

Also available: Docker Compose (`docker compose up --build` from this repo
root) — see [docs/03-developer-setup.md](docs/03-developer-setup.md).

Open http://localhost:3000. API documentation is at http://localhost:8000/docs.

## Configuration

Backend environment variables (`backend/.env`):

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | Database connection | `sqlite:///./infrawatch.db` |
| `SATELLITE_MODE` | `demo` for bundled images or `real` to delegate to satellite-service | `demo` |
| `SATELLITE_SERVICE_URL` | Where satellite-service is reachable (only used in `real` mode) | `http://localhost:8001` |
| `GEMINI_API_KEY` | Enables Gemini image analysis (demo-mode analyzer) | empty |
| `AI_VISION_MODEL` | Gemini model identifier | `gemini-2.5-flash-lite` |
| `CORS_ORIGINS` | Comma-separated allowed browser origins | `http://localhost:3000` |

Frontend environment variables (`frontend/.env.local`):

| Variable | Purpose | Default |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Backend URL | `http://localhost:8000` |

## API

Full reference (including satellite-service's API) is in
[docs/05-architecture-and-api-reference.md](docs/05-architecture-and-api-reference.md).

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | API and database health check |
| GET | `/api/projects` | Project list (includes each project's latest satellite image URL) |
| POST | `/api/projects` | Create a new project |
| GET | `/api/projects/kpi-summary` | Dashboard status counts |
| GET | `/api/projects/{id}` | Project detail |
| POST | `/api/projects/{id}/analyze` | Analyze the project image pair |
| POST | `/api/projects/{id}/ingest` | Force a fresh real-imagery fetch |
| GET | `/api/projects/{id}/evidence` | Latest screening evidence |

## Testing

```bash
cd backend
pytest tests/ -v
```

12 tests covering health, project listing/detail (including the
`latest_image_url` field), image-change detection, GeoJSON conversion,
fallback analysis, the demo-mode analysis workflow, and the
satellite-service integration layer (HTTP client, response-mapping, and
graceful degradation on failure — all mocked, no network needed). The
frontend has no automated tests yet; see
[docs/04-testing-and-qa.md](docs/04-testing-and-qa.md) for the manual QA
checklist that covers it instead.

## Limitations

- Bundled images are demo assets, not evidence from a live government system.
- Pixel differences can be caused by lighting, clouds, shadows, seasonal
  vegetation, or image alignment; every result requires field verification.
- The prototype does not yet include authentication, roles, or production
  security controls.
