# InfraWatch

InfraWatch is an SIH26102 prototype that helps government reviewers screen
MPLADS (Members of Parliament Local Area Development Scheme) infrastructure
works by comparing a project's *self-reported* progress against
*observable* change between two images of the site. It is a decision-support
screening tool, not a fraud-detection system — every result is a
prioritization signal for human field verification, never a finding of
guilt or statutory violation.

This repository holds the full-stack application: a FastAPI backend, a
Next.js dashboard, and JWT-based authentication with two roles (analyst and
contractor). A separate sibling microservice, **satellite-service**, does
the actual Sentinel-2 imagery fetch and pretrained-model change detection.

**Want to just run it? Put this repo next to a `satellite-service` folder
(same parent directory) and run:**

```bash
./start-all.sh
```

That's the entire setup — no manual database, dataset, or account step. On
first boot the backend automatically seeds 6 offline demo projects, the
real ~1,000-row MPLADS registry (including 4 projects with real
manually-photographed before/after evidence), and one demo analyst + one
demo contractor account. First run takes a few minutes (installs
everything); every run after that takes seconds. See
[docs/00-quickstart.md](docs/00-quickstart.md) if anything about that isn't
obvious.

**New to this project? Start in
[`docs/01-project-overview.md`](docs/01-project-overview.md)** instead of
this file. This README is a quick reference; the `docs/` folder has the
full walkthrough:

| Doc | For |
|---|---|
| [docs/00-quickstart.md](docs/00-quickstart.md) | The one command to run everything — start here |
| [docs/01-project-overview.md](docs/01-project-overview.md) | What this project is, the problem it solves, what's real vs. synthetic |
| [docs/02-user-guide.md](docs/02-user-guide.md) | Using the dashboard as an analyst, and the workflow as a contractor |
| [docs/03-developer-setup.md](docs/03-developer-setup.md) | Cloning, installing, running and testing this from scratch |
| [docs/04-testing-and-qa.md](docs/04-testing-and-qa.md) | Automated test coverage + manual QA checklist |
| [docs/05-architecture-and-api-reference.md](docs/05-architecture-and-api-reference.md) | System diagram, full API reference, data model, design rationale |
| [docs/06-auth-and-roles.md](docs/06-auth-and-roles.md) | JWT auth flow, the analyst/contractor roles, and how role gating works |
| [docs/MERGE-NOTES.md](docs/MERGE-NOTES.md) | What was kept vs. discarded from an earlier branch's contributions |

## Architecture

```text
Next.js dashboard  ⇄  InfraWatch FastAPI backend  ⇄  satellite-service (separate microservice)
      ↑                       ↓        ↓                        ↓
 Leaflet map +        SQLite/PostgreSQL  JWT auth        Sentinel-2 fetch → pretrained
 GeoJSON overlay      (projects, users,  (bcrypt +       CNN feature-diff change
                       risk evidence)    python-jose)     detection → Gemini/template
                                                           narration
```

Three services, three concerns:

- **frontend/** — Next.js + TypeScript dashboard: analyst registry/map/detail
  views and a contractor portal (register project, upload evidence).
- **backend/** — FastAPI: auth, the project registry, the deterministic risk
  engine, and orchestration of whichever evidence pipeline a given project
  uses (real satellite, manually-uploaded photos, or "not yet available").
- **satellite-service/** (sibling repo, `../satellite-service`) — standalone
  microservice that fetches real Sentinel-2 10m bands, runs a pretrained
  ResNet18 feature-diff change-detection model ("PlanAura"), and narrates the
  result with Gemini (or a template fallback). It also exposes
  `/model/detect-images`, used to score manually-uploaded before/after
  photos with the same model, for projects that have no GPS coordinate.

See [docs/05-architecture-and-api-reference.md](docs/05-architecture-and-api-reference.md)
for the full request-flow breakdown and API tables.

## What's real vs. synthetic in the data

- **Real**: a ~1,000-row MPLADS works dataset (`backend/data/processed/mplads_normalized.csv`,
  sourced from the government MPLADS/MoSPI portal), imported honestly —
  most rows have no published GPS coordinate, which is the normal state of
  this kind of open government data, not a bug. 4 real legacy projects
  additionally have real manually-photographed before/after evidence (3 Goa/
  Nagaland small works from the CSV, plus one standalone Tamil Nadu example
  not in the CSV).
- **Synthetic**: 6 bundled `[DEMO]` projects with fabricated coordinates and
  bundled demo image pairs, used so the dashboard has something to show with
  zero network access. Clearly labeled `is_demo=1` and named with a `[DEMO]`
  prefix.
- **Optional**: a 24-project real PMGSY facility-location sample
  (`satellite-service/samples/pmgsy_real_projects.csv`) can be imported via
  `backend/scripts/import_pmgsy_csv.py` — real facility locations, but with a
  synthetic placeholder `reported_progress` (these are existing operational
  facilities, not in-progress works with a genuine self-reported completion
  claim).

## Auth and roles

JWT-based authentication (`python-jose` + `passlib`/bcrypt password hashing).
Two roles:

- **analyst** — sees the full project registry (paginated, filterable by
  data source / evidence source), opens project detail pages, runs
  screening analysis, views the risk breakdown, exports a PDF field report.
- **contractor** — registers new projects (GPS coordinates mandatory — every
  new project gets real satellite screening from day one) and uploads
  before/after evidence photos for existing no-coordinate legacy projects
  they own.

Two demo accounts are seeded automatically for local evaluation only —
**never reuse these for a real deployment**:

| Role | Email | Password |
|---|---|---|
| Analyst | `analyst@infrawatch.local` | `demo-analyst-2025` |
| Contractor | `contractor@infrawatch.local` | `demo-contractor-2025` |

Full details: [docs/06-auth-and-roles.md](docs/06-auth-and-roles.md).

## Technology

- Frontend: Next.js 14, TypeScript, Tailwind CSS, Leaflet, jsPDF
- Backend: Python, FastAPI, SQLAlchemy, Pydantic, python-jose, passlib/bcrypt
- Image processing (demo-mode fallback path): OpenCV, Rasterio, NumPy
- satellite-service: rasterio (real Sentinel-2 10m bands via STAC), a
  pretrained ResNet18 feature-diff model, Gemini narration
- Database: PostgreSQL + PostGIS for deployment; SQLite for local dev (the
  ORM stores geometry as portable WKT text so the same model code runs
  against either)

## Run locally

**Recommended — one command, everything automatic** (requires
`satellite-service` cloned as a sibling folder next to this repo):

```bash
./start-all.sh          # demo mode: bundled images, no internet needed
./start-all.sh real     # real mode: live Sentinel-2 imagery via satellite-service
```

**Manual, piece by piece** — backend:

```bash
cd backend
./setup.sh   # or manually: python3 -m venv .venv && source .venv/bin/activate
             # && pip install -r requirements.txt && cp .env.example .env
./run.sh     # or: uvicorn app.main:app --reload --port 8000
```

Frontend, in a second terminal:

```bash
cd frontend
./setup.sh   # or: cp .env.example .env.local && npm install
./run.sh     # or: npm run dev
```

For real Sentinel-2 imagery (instead of bundled demo images), also run
satellite-service (`./setup.sh && uvicorn app:app --reload --port 8001` in
that repo) and set `SATELLITE_MODE=real` in `backend/.env`.

Also available: Docker Compose (`docker compose up --build` from this repo
root) — see [docs/03-developer-setup.md](docs/03-developer-setup.md).

Open http://localhost:3000. API documentation is at http://localhost:8000/docs.

## Configuration

Backend environment variables (`backend/.env`) — see
[docs/03-developer-setup.md](docs/03-developer-setup.md) for the full list;
the ones most worth knowing about:

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | Database connection | `sqlite:///./infrawatch.db` |
| `SATELLITE_MODE` | `demo` for bundled images or `real` to delegate to satellite-service | `demo` |
| `SATELLITE_SERVICE_URL` | Where satellite-service is reachable (`real` mode only) | `http://localhost:8001` |
| `JWT_SECRET_KEY` | Signs auth tokens — **must** be overridden for any deployment beyond one developer's machine | dev-only insecure default |
| `GEMINI_API_KEY` | Enables Gemini narration in satellite-service (falls back to a template otherwise) | empty |
| `CORS_ORIGINS` | Comma-separated allowed browser origins | `http://localhost:3000` |

Frontend (`frontend/.env.local`): `NEXT_PUBLIC_API_BASE_URL` (default
`http://localhost:8000`).

## API

Full reference (including satellite-service's API) is in
[docs/05-architecture-and-api-reference.md](docs/05-architecture-and-api-reference.md).

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/health` | none | API and database health check |
| POST | `/api/auth/register` | none | Create an account (analyst or contractor) |
| POST | `/api/auth/login` | none | Exchange credentials for a JWT |
| GET | `/api/auth/me` | any authenticated user | Current user's profile |
| GET | `/api/projects` | any authenticated user | Paginated project registry, with filters |
| GET | `/api/projects/mine` | contractor | The calling contractor's own projects |
| POST | `/api/projects` | contractor | Register a new project (GPS mandatory) |
| POST | `/api/projects/{id}/evidence/upload` | contractor | Upload before/after photos for a no-coordinate project |
| GET | `/api/projects/kpi-summary` | any authenticated user | Dashboard status counts |
| GET | `/api/projects/{id}` | any authenticated user | Project detail |
| GET | `/api/projects/{id}/risk` | any authenticated user | Composite risk score and factor breakdown |
| POST | `/api/projects/{id}/analyze` | any authenticated user | Run/re-run the screening pipeline |
| POST | `/api/projects/{id}/ingest` | any authenticated user | Force a fresh imagery fetch + analysis |
| GET | `/api/projects/{id}/evidence` | any authenticated user | Latest screening evidence summary |

All `/api/projects...` routes require a logged-in account (analyst or
contractor) — there is no anonymous read access to the registry.

## Testing

```bash
cd backend
pytest tests/ -v
```

25 tests covering authentication (register/login/role enforcement,
password hashing), the risk engine (deterministic scoring, and an explicit
test that its satellite-discrepancy function takes no `project_id` and so
cannot be special-cased per project), project CRUD, and the satellite-service
integration layer (HTTP client, response mapping, graceful degradation —
mocked, no network needed).

The frontend has no automated test runner configured yet; `npx tsc --noEmit`
in `frontend/` is used as a type-correctness check. See
[docs/04-testing-and-qa.md](docs/04-testing-and-qa.md) for the full picture,
including the manual QA checklist.

## Limitations

- Bundled demo images are synthetic assets, not evidence from a live
  government system — they exist purely so the dashboard has something to
  show offline.
- Pixel/feature differences can be caused by lighting, clouds, shadows,
  seasonal vegetation, or image alignment — every HIGH/CRITICAL result
  requires field verification, not automatic action.
- No production security hardening (rate limiting, audit logging UI,
  password reset flow, refresh tokens) beyond JWT + bcrypt auth and role
  gating — see [docs/06-auth-and-roles.md](docs/06-auth-and-roles.md).
- The risk engine's thresholds and weights are reasoned defaults, not
  calibrated against a labeled ground-truth dataset of confirmed
  fraud/non-fraud cases.
