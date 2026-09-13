from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import settings
from app.database import Base, engine, SessionLocal
from app.models.models import Project
from app.api import health, projects, auth
from scripts.seed_demo_data import seed
from scripts.seed_real_mplads import seed as seed_real_mplads
from scripts.seed_demo_users import seed as seed_demo_users

import sys

ASSET_DIR = Path(__file__).resolve().parent / "demo_assets"
MANUAL_EVIDENCE_DIR = Path(__file__).resolve().parent / "manual_evidence"
MANUAL_EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)

Base.metadata.create_all(bind=engine)

if "pytest" not in sys.modules:
    db = SessionLocal()
    try:
        # Only on a genuinely empty database — seed_demo_data() itself is
        # NOT idempotent (it wipes and re-seeds unconditionally), so this
        # guard is what keeps a container restart from ever nuking real
        # imported data. Runs once, automatically, on first boot.
        if db.query(Project).count() == 0:
            seed()
            seed_real_mplads()
        seed_demo_users()
    finally:
        db.close()

app = FastAPI(
    title=settings.api_title,
    version=settings.api_version,
    description=(
        "AI-assisted decision-support system for detecting anomalies, "
        "irregularities and inefficiencies in MPLADS infrastructure "
        "implementation. Outputs are recommendations for human field "
        "verification, not findings of fraud or guilt."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(health.router)
app.include_router(auth.router)
app.include_router(projects.router)
app.mount("/demo-assets", StaticFiles(directory=str(ASSET_DIR)), name="demo-assets")
app.mount("/manual-evidence", StaticFiles(directory=str(MANUAL_EVIDENCE_DIR)), name="manual-evidence")
