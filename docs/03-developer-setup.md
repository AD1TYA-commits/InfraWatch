# Developer Setup — Run and Build This From Scratch

## 0. What you're setting up

Three independently-runnable services:

| Service | Folder | Port | Stack |
|---|---|---|---|
| Frontend | `InfraWatch/frontend/` | 3000 | Next.js 14 + TypeScript + Tailwind |
| Backend | `InfraWatch/backend/` | 8000 | FastAPI + SQLAlchemy + SQLite/Postgres |
| satellite-service | `satellite-service/` (sibling repo) | 8001 | FastAPI + rasterio + pretrained CNN |

`InfraWatch` and `satellite-service` must be sibling folders under the same
parent directory — `start-all.sh`, `backend/.env.example`, and
`docker-compose.yml` all assume this layout.

## 1. Prerequisites

- Python 3.10+
- Node.js 18+ and npm
- (Optional, for Docker Compose) Docker + Docker Compose

No database server install is required for local dev — SQLite is the
zero-setup default. Docker Compose uses PostGIS instead (see below).

## 2. Get both codebases

```bash
git clone https://github.com/AD1TYA-commits/InfraWatch.git InfraWatch
git clone https://github.com/chiragawasthi17/satellite-service.git satellite-service
# both now sit as siblings under the same parent directory
```

## 3. Run everything — the automated one-command way (recommended)

```bash
cd InfraWatch
./start-all.sh
```

See [00-quickstart.md](00-quickstart.md) for full detail on what this does
and how to read the logs it writes to `/tmp/infrawatch-logs/`.

## 4. Run everything manually (useful for understanding, or active development on one piece)

satellite-service:

```bash
cd satellite-service
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # optionally set GEMINI_API_KEY
uvicorn app:app --reload --port 8001
```

InfraWatch backend, in a second terminal:

```bash
cd InfraWatch/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000
```

The database is created and auto-seeded (the 4 real manual-evidence
projects, demo accounts) the first time the app starts against an empty
database — see `app/main.py`. satellite-service must be running and
reachable at `SATELLITE_SERVICE_URL` for any coordinate-based project's
analysis to work — there is no offline fallback.

InfraWatch frontend, in a third terminal:

```bash
cd InfraWatch/frontend
cp .env.example .env.local
npm install
npm run dev
```

## 3b. Run everything with Docker Compose (alternative — no local Python/Node needed at all)

```bash
cd InfraWatch
docker compose up --build
```

This starts PostgreSQL+PostGIS, the backend, satellite-service, and the
frontend as containers (see `docker-compose.yml`). The backend's
`DATABASE_URL` is set to the Postgres container automatically; the same
SQLAlchemy ORM code runs unchanged (geometry is stored as WKT text at the
ORM layer either way — see the note in `backend/app/models/models.py`).
Auto-seeding is guarded the same way as local dev: it only runs against a
genuinely empty database, so re-running `docker compose up` against an
existing volume never re-seeds or wipes data. Set `GEMINI_API_KEY` as an
environment variable before `up` for Gemini narration in satellite-service
(otherwise it falls back to a template).

## 5. Environment variables reference

### `InfraWatch/backend/.env`

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | DB connection string | `sqlite:///./infrawatch.db` |
| `SATELLITE_SERVICE_URL` | Base URL of the satellite-service microservice — every coordinate-based project is analyzed by calling out to it | `http://localhost:8001` |
| `CORS_ORIGINS` | Comma-separated allowed browser origins | `http://localhost:3000` |
| `JWT_SECRET_KEY` | Signs and verifies auth tokens | `dev-only-insecure-secret-change-me` — **override this for any deployment reachable beyond your own machine** (e.g. `openssl rand -hex 32`); present in `.env.example` with this insecure default precisely so a deployment doesn't silently ship without one |
| `JWT_EXPIRE_MINUTES` | Token lifetime | `10080` (7 days) |

Note: `JWT_ALGORITHM` is fixed to `HS256` in code (`app/config.py`), not
environment-configurable.

### `InfraWatch/frontend/.env.local`

| Variable | Purpose | Default |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Backend base URL | `http://localhost:8000` |

### `satellite-service/.env`

| Variable | Purpose | Default |
|---|---|---|
| `WINDOW_KM` | AOI half-width fetched around each project, km | `1.28` |
| `OUTPUT_SIZE_PX` | Output raster size in pixels | `256` |
| `MAX_CLOUD_PERCENTAGE` | STAC cloud-cover filter | `20` |
| `CHANGE_MIN_CONFIDENCE` | Heatmap threshold for "changed" | `0.35` |
| `CHANGE_MIN_AREA_PX` | Minimum candidate region size, pixels | `40` |
| `GEMINI_API_KEY` | Enables Gemini narration; empty = template fallback | empty |

## 6. Project structure — where things live

```text
InfraWatch/
├── backend/
│   ├── app/
│   │   ├── main.py                 # app wiring, CORS, static mounts, auto-seed on boot
│   │   ├── config.py                # Settings (env vars) + RISK_WEIGHTS
│   │   ├── auth.py                  # JWT + bcrypt, get_current_user, require_role
│   │   ├── risk_engine.py            # deterministic composite risk scoring
│   │   ├── models/models.py          # SQLAlchemy ORM models
│   │   ├── schemas/schemas.py        # Pydantic request/response models
│   │   ├── api/
│   │   │   ├── auth.py               # /api/auth/*
│   │   │   ├── projects.py           # /api/projects/* + pipeline orchestration
│   │   │   └── health.py             # /api/health
│   │   ├── satellite_service_client.py    # HTTP client for satellite-service /pipeline/run
│   │   ├── manual_evidence_client.py      # HTTP client for satellite-service /model/detect-images
│   │   └── manual_evidence/           # contractor-uploaded + seeded real evidence photos
│   ├── data/processed/mplads_normalized.csv   # the real ~1,000-row MPLADS CSV (reference data —
│   │                                           # only 3 rows with a verified coordinate become projects)
│   ├── scripts/
│   │   ├── seed_real_mplads.py        # imports the 3 geolocated MPLADS CSV rows + attaches
│   │   │                             # real manual evidence (4 projects total incl. Tamil Nadu)
│   │   ├── seed_demo_users.py         # the 2 demo accounts
│   │   └── import_pmgsy_csv.py        # optional: 24 real PMGSY facility locations, via the real HTTP API
│   └── tests/                        # pytest (23 tests across 3 files) — see 04-testing-and-qa.md
├── frontend/
│   ├── app/{login,register,contractor,projects/[id]}/page.tsx, page.tsx (dashboard), layout.tsx
│   ├── components/{AuthProvider,Dashboard,ProjectDetailView,ProjectMap,KpiCards,...}.tsx
│   ├── lib/{api.ts,pdfReport.ts}
│   └── types/project.ts
├── start-all.sh
├── docker-compose.yml
└── docs/
```

## 7. Common developer tasks

**Run backend tests:**

```bash
cd backend && pytest tests/ -v
```

**Type-check the frontend** (no automated test runner is configured yet):

```bash
cd frontend && npx tsc --noEmit
```

**Re-seed from scratch (destroys local data):**

```bash
cd backend
rm -f infrawatch.db
python -m scripts.seed_real_mplads
python -m scripts.seed_demo_users
```

(Just restarting the backend against an empty database does the same thing
automatically — see `app/main.py`.)

**Import the optional real PMGSY sample** (backend must already be running):

```bash
cd backend
python -m scripts.import_pmgsy_csv                      # default CSV path + localhost:8000
python -m scripts.import_pmgsy_csv --skip-analyze        # create projects without running analysis yet
```

## 8. Troubleshooting

- **`ModuleNotFoundError` running a script under `scripts/`** — run it as a
  module from `backend/` (`python -m scripts.seed_real_mplads`), not as a bare
  script path; the scripts insert the backend root onto `sys.path`
  themselves but expect to be invoked from there.
- **bcrypt/passlib import errors** — `requirements.txt` deliberately pins
  `bcrypt<4.1` because passlib 1.7.4's bcrypt handler is incompatible with
  bcrypt≥4.1's removed `__about__` attribute; reinstall with
  `pip install -r requirements.txt` if you've bumped bcrypt independently.
- **401 on every API call from the frontend** — check `localStorage` for an
  `infrawatch_token` key; log out and back in if the token has expired
  (default lifetime 7 days) or `JWT_SECRET_KEY` changed since it was issued.
- **Analysis requests hang or 502** — confirm satellite-service is actually
  running on port 8001 and reachable at `SATELLITE_SERVICE_URL`; check
  `satellite-service.log`. There is no offline fallback — satellite-service
  must be up for any coordinate-based project's analysis to succeed.
- **Windows: connections to `localhost` time out for ~30s** — the frontend's
  `lib/api.ts` normalizes `localhost` to `127.0.0.1` specifically to avoid
  this (an IPv6 `::1` resolution delay); if you still see it, check your
  `NEXT_PUBLIC_API_BASE_URL` isn't overriding that.
