# Developer Setup — Run and Build This From Scratch

This walks a developer with zero prior context through getting the entire
system (InfraWatch + satellite-service) running locally, understanding the
codebase layout, and making common changes. If you just want to *use* the
app, see [02-user-guide.md](02-user-guide.md) instead.

## 0. What you're setting up

Two separate projects that talk to each other over HTTP:

```
some-folder/
├── InfraWatch/            (this repo — dashboard + backend)
│   ├── backend/           FastAPI + SQLAlchemy + SQLite/Postgres
│   ├── frontend/          Next.js + TypeScript + Leaflet
│   └── docs/              you are here
└── satellite-service/     (sibling repo/folder — satellite fetch + ML model)
```

They must be **sibling folders** (same parent directory) for the default
configuration to line up — `docker-compose.yml` references
`../satellite-service` as a build context.

## 1. Prerequisites

| Tool | Needed for | Check with |
|---|---|---|
| Python 3.10+ | Both backends | `python3 --version` |
| Node.js 18+ | Frontend | `node --version` |
| npm | Frontend | `npm --version` |
| Git | Cloning | `git --version` |
| Docker + Docker Compose | Optional, for the one-command setup | `docker --version` |

On macOS, if `rasterio` (used by both backends for satellite imagery) fails
to install, install GDAL first: `brew install gdal`.

## 2. Get both codebases

```bash
git clone <infrawatch-repo-url> InfraWatch
git clone <satellite-service-repo-url> satellite-service
```
(Put them side by side, as shown above.)

## 3. Run everything — the automated one-command way (recommended)

```bash
cd InfraWatch
./start-all.sh          # demo mode (default): bundled images, no internet needed
./start-all.sh real     # real mode: live Sentinel-2 imagery via satellite-service
```

This is a plain bash script (`start-all.sh` at the repo root) that does
everything the manual steps in §4 do, automatically and in the right order:
- Creates each service's virtualenv/`node_modules` on first run only (checks
  if they already exist — safe to re-run any time, later runs skip straight
  to starting).
- Copies each `.env.example` to a working `.env`/`.env.local` if one isn't
  there yet — no environment variables need hand-editing for a working demo.
- Flips `SATELLITE_MODE` between `demo`/`real` based on the argument you
  pass, by editing `backend/.env` itself (`sed`) — you never touch that file.
- Starts satellite-service (8001), the InfraWatch backend (8000, which
  auto-seeds its demo database and 6 sample projects the moment it starts —
  nothing to prepare or download by hand), and the frontend (3000).
- Prints all three URLs once they're up, and where their logs are
  (`/tmp/infrawatch-logs/`) if something looks wrong.
- `Ctrl+C` stops all three cleanly (kills whatever is bound to ports
  8000/8001/3000, not just the wrapper processes — verified to actually
  free the ports, not just look like it stopped).

Each sub-project also has its own `setup.sh` (one-time install) and `run.sh`
(start just that one) if you want to run a single piece on its own —
`start-all.sh` is just those three, orchestrated.

## 4. Run everything manually (useful for understanding, or active development on one piece)

Manual setup gives faster reload loops and clearer error messages while
you're actively changing one service's code. Three terminals — this is
exactly what `./start-all.sh` automates for you:

**Terminal 1 — satellite-service:**
```bash
cd satellite-service
./setup.sh   # first time only — creates .venv, installs deps, copies .env
./run.sh     # or manually: source .venv/bin/activate && uvicorn app:app --reload --port 8001
```
(First run downloads pretrained model weights — a one-time delay of a few
seconds to a minute depending on your connection.)

**Terminal 2 — InfraWatch backend:**
```bash
cd InfraWatch/backend
./setup.sh   # first time only
# Edit .env: set SATELLITE_MODE=real to test against real satellite imagery;
#   leave SATELLITE_MODE=demo for zero-network, instant startup using bundled
#   demo images (this is the default already in .env.example).
./run.sh     # or manually: source .venv/bin/activate && uvicorn app.main:app --reload --port 8000
```
The database auto-creates and seeds 6 demo projects on first run (SQLite
file `infrawatch.db`, zero setup needed).

**Terminal 3 — Frontend:**
```bash
cd InfraWatch/frontend
./setup.sh   # first time only
./run.sh     # or manually: npm run dev
```
Open http://localhost:3000.

## 3b. Run everything with Docker Compose (alternative — no local Python/Node needed at all)

```bash
cd InfraWatch
cp backend/.env.example backend/.env       # edit if you have a Gemini key
docker compose up --build
```

This starts, in order: a PostGIS-enabled Postgres database, the
satellite-service microservice, the InfraWatch backend (seeding demo
projects on first boot), and the Next.js frontend. Once it's up:
- Frontend: http://localhost:3000
- Backend API + docs: http://localhost:8000/docs
- satellite-service API docs: http://localhost:8001/docs

Set `SATELLITE_MODE=real` (as an environment variable before `docker compose
up`, or in `backend/.env`) to have every project analyzed against live
Sentinel-2 imagery instead of bundled demo images.

Use this instead of `./start-all.sh` if you'd rather not install
Python/Node locally at all — Docker Desktop is the only prerequisite. It's
slower to first build (several minutes, mostly satellite-service's
PyTorch/GDAL image) but the containers are then fully isolated from your
machine's own Python/Node setup.

## 5. Environment variables reference

### `InfraWatch/backend/.env`

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | DB connection string | `sqlite:///./infrawatch.db` |
| `SATELLITE_MODE` | `demo` (bundled images) or `real` (live satellite-service calls) | `demo` |
| `SATELLITE_SERVICE_URL` | Where satellite-service is reachable | `http://localhost:8001` |
| `GEMINI_API_KEY` | Enables Gemini narration in the legacy demo-mode analyzer | empty |
| `AI_VISION_MODEL` | Gemini model id (demo-mode analyzer only) | `gemini-2.5-flash-lite` |
| `CORS_ORIGINS` | Comma-separated browser origins allowed to call this API | `http://localhost:3000` |

### `InfraWatch/frontend/.env.local`

| Variable | Purpose | Default |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | InfraWatch backend URL | `http://localhost:8000` |

### `satellite-service/.env`

See satellite-service's own `.env.example` and `docs/02-getting-started.md`
— key ones are `GEMINI_API_KEY` (optional; falls back to a templated
summary without it), `WINDOW_KM` / `OUTPUT_SIZE_PX` (AOI size and imagery
resolution), and `CHANGE_MIN_CONFIDENCE` (detection sensitivity).

## 6. Project structure — where things live

```
backend/app/
├── main.py                     FastAPI app entrypoint, CORS, static file mounts
├── config.py                   All settings (reads .env)
├── database.py                 SQLAlchemy engine/session setup
├── models/models.py             DB tables (Project, Milestone, SatelliteObservation, ...)
├── schemas/schemas.py           Pydantic request/response shapes (the API contract)
├── api/projects.py              All /api/projects/* routes + the analysis pipeline
├── satellite_service_client.py  HTTP client for the satellite-service microservice
├── satellite_provider.py        Legacy Sentinel-2/Esri fetch (demo-mode path only)
├── imagery_processor.py         Legacy raster download/crop (demo-mode path only)
├── change_detector.py           Legacy OpenCV pixel-diff detector (demo-mode path only)
├── change_analyzer.py           Legacy Gemini/fallback analyzer (demo-mode path only)
├── geo_processor.py             Legacy candidates -> GeoJSON (demo-mode path only)
└── demo_assets/                 Bundled before/after PNGs for the 6 seeded demo projects

frontend/
├── app/                          Next.js routes: app/page.tsx (dashboard), app/projects/[id]/page.tsx
├── components/                   Dashboard, ProjectMap, ProjectDetailView, KpiCards, StatusBadge, ThemeToggle
│   └── BeforeAfterSlider.tsx      Drag-to-reveal T1/T2 comparison + change-region highlight overlay
├── lib/api.ts                    All backend API calls + resolveAssetUrl() helper
├── lib/pdfReport.ts               Client-side (jsPDF) field-verification report generator
└── types/project.ts              TypeScript types mirroring the backend's Pydantic schemas
```

> **Why do "legacy" files still exist?** They're still the live code path
> for `SATELLITE_MODE=demo` (bundled-image demos need no network and no
> external service). Only the *real*-mode path was replaced by
> satellite-service — see
> [05-architecture-and-api-reference.md](05-architecture-and-api-reference.md)
> for exactly how `api/projects.py` branches between the two.

## 7. Common developer tasks

**Re-seed the demo database from scratch:**
```bash
cd backend && rm -f infrawatch.db && python -m scripts.seed_demo_data
```

**Run the automated test suites:**
```bash
cd backend && pytest tests/ -v
cd ../../satellite-service && pytest tests/ -v
```
See [04-testing-and-qa.md](04-testing-and-qa.md) for what's covered and the
manual QA checklist (the frontend has no automated tests yet).

**Add a real project to check:**
Use `POST /api/projects` (see the API reference) to create one, then
`POST /api/projects/{id}/analyze` to run it — this is the same path the
dashboard uses, no direct DB access needed.

**Bulk-import a real-world project list:** see
`backend/scripts/import_pmgsy_csv.py` — it reads a CSV (name, latitude,
longitude, project_type, reported_progress) and creates + analyzes each row
via the real API. It ships pointed at
`satellite-service/samples/pmgsy_real_projects.csv` by default: 24 real,
publicly-sourced facility locations (schools, health centres, panchayat
offices) from India's PMGSY open data — genuinely real coordinates, useful
for testing `SATELLITE_MODE=real` against actual Sentinel-2 imagery instead
of the synthetic demo locations. Run it with:
```bash
cd backend && source .venv/bin/activate
python -m scripts.import_pmgsy_csv
```
Point it at any other CSV in the same shape to import a different list.

**Type-check the frontend before committing:**
```bash
cd frontend && npx tsc --noEmit
```

## 8. Troubleshooting

**Frontend shows "Unable to reach InfraWatch Backend"** — the backend isn't
running, or `NEXT_PUBLIC_API_BASE_URL` doesn't match where it's listening.
Check `curl http://localhost:8000/api/health`.

**A project's analysis takes 10-30 seconds and briefly errors before
succeeding** — expected on `SATELLITE_MODE=real`: it's a genuine live
satellite fetch + model run, not instant like demo mode. If it errors
permanently (not just slow), check satellite-service is actually running
(`curl http://localhost:8001/health`) and reachable at the URL configured
in `SATELLITE_SERVICE_URL`.

**`rasterio`/GDAL install fails** — see Prerequisites above; install GDAL
via your OS package manager first, then retry `pip install -r
requirements.txt`.

**Map controls or a modal render on top of the navbar** — this was a real
bug (Leaflet's internal z-index of up to 1000 escaping past the sticky
header's lower z-index with no containing stacking context in between) and
is now fixed in `app/layout.tsx` (header z-index raised above 1000) and
`components/ProjectMap.tsx` (`isolate` class added to contain the map's
stacking context). If you see this again after adding a new
high-z-index overlay elsewhere, check it lives inside an `isolate`d
container, not directly under `<main>`.
