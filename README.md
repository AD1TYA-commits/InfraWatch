# InfraWatch

InfraWatch is an SIH26102 prototype for helping officials compare reported
MPLADS project progress with observable change between two images. It provides
screening evidence for human review; it does not make fraud or guilt findings.

## Current scope

The application includes a FastAPI backend, Next.js dashboard, project map,
SQLite demo database, bundled before/after image pairs, local OpenCV change
detection, and an optional Gemini analysis step. All seeded projects and image
pairs are demo data.

| Area | Status |
|---|---|
| Dashboard, map, project details, API and demo data | Available |
| Image comparison, change mask and GeoJSON overlay | Available for bundled demo image pairs |
| Gemini analysis | Optional; requires `GEMINI_API_KEY` |
| Live Sentinel-2 ingestion | Prototype integration; validate before operational use |
| Login, user management and role-based access control | Planned |
| Secure sessions, password protection, authorization and audit controls | Planned before production use |
| Validated ML model training and evaluation | Planned |

## Architecture

```text
PostgreSQL + PostGIS (production) / SQLite (local demo)
                         ↓
                      FastAPI API
                         ↓
                 Next.js dashboard and map
                         ↑
       Image pair → OpenCV change detection → optional Gemini analysis
```

## Technology

- Frontend: Next.js, TypeScript, Tailwind CSS, Leaflet
- Backend: Python, FastAPI, SQLAlchemy, Pydantic
- Image processing: OpenCV, Rasterio, NumPy, GeoPandas, Shapely
- Database: PostgreSQL with PostGIS for deployment; SQLite for local demo

## Run locally

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m scripts.seed_demo_data
uvicorn app.main:app --reload --port 8000
```

Frontend, in a second terminal:

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

Open http://localhost:3000. API documentation is at http://localhost:8000/docs.

## Configuration

Backend environment variables (`backend/.env`):

| Variable | Purpose | Default |
|---|---|---|
| `DATABASE_URL` | Database connection | `sqlite:///./infrawatch.db` |
| `SATELLITE_MODE` | `demo` for bundled images or `real` for STAC lookup | `demo` |
| `GEMINI_API_KEY` | Enables Gemini image analysis | empty |
| `AI_VISION_MODEL` | Gemini model identifier | `gemini-2.5-flash-lite` |
| `CORS_ORIGINS` | Comma-separated allowed browser origins | `http://localhost:3000` |

Frontend environment variables (`frontend/.env.local`):

| Variable | Purpose | Default |
|---|---|---|
| `NEXT_PUBLIC_API_BASE_URL` | Backend URL | `http://localhost:8000` |

## API

| Method | Path | Description |
|---|---|---|
| GET | `/api/health` | API and database health check |
| GET | `/api/projects` | Project list |
| GET | `/api/projects/kpi-summary` | Dashboard status counts |
| GET | `/api/projects/{id}` | Project detail |
| POST | `/api/projects/{id}/analyze` | Analyze the project image pair |
| GET | `/api/projects/{id}/evidence` | Latest screening evidence |

## Testing

```bash
cd backend
pytest tests/ -v
```

The test suite covers health, project listing/detail, image-change detection,
GeoJSON conversion, fallback analysis, and the analysis API workflow.

## Limitations

- Bundled images are demo assets, not evidence from a live government system.
- Pixel differences can be caused by lighting, clouds, shadows, seasonal
  vegetation, or image alignment; every result requires field verification.
- The prototype does not yet include authentication, roles, or production
  security controls.
