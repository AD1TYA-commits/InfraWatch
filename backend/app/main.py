from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.config import settings
from app.database import Base, engine, SessionLocal
from app.models.models import Project
from app.api import health, projects
from scripts.seed_demo_data import seed

import sys

ASSET_DIR = Path(__file__).resolve().parent / "demo_assets"

Base.metadata.create_all(bind=engine)

if "pytest" not in sys.modules:
    db = SessionLocal()
    try:
        if db.query(Project).count() == 0:
            seed()
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
app.include_router(projects.router)
app.mount("/demo-assets", StaticFiles(directory=str(ASSET_DIR)), name="demo-assets")
