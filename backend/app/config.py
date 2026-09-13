"""
Central configuration for InfraWatch backend.

All environment-driven settings live here, plus the risk engine's composite
weights (see RISK_WEIGHTS below) so nothing in app/risk_engine.py is an
unexplained inline magic number.
"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Database. Defaults to a local SQLite file so the MVP runs with zero
    # external services. In production / Docker, set DATABASE_URL to a
    # PostgreSQL+PostGIS connection string, e.g.:
    #   postgresql+psycopg2://infrawatch:infrawatch@db:5432/infrawatch
    database_url: str = os.getenv("DATABASE_URL", "sqlite:///./infrawatch.db")

    # Standalone satellite-service microservice (separate repo/folder) — real
    # Sentinel-2 fetch + pretrained-model change detection. Every
    # coordinate-based project is analyzed by calling out to this service.
    satellite_service_url: str = os.getenv("SATELLITE_SERVICE_URL", "http://localhost:8001")

    # Comma-separated browser origins permitted to call this API.
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:3000")

    # API metadata
    api_title: str = "InfraWatch API"
    api_version: str = "0.1.0-mvp"

    # Auth. JWT_SECRET_KEY MUST be overridden via env var for any deployment
    # beyond a single developer's machine — the default here only exists so
    # local dev works with zero setup, never reuse it anywhere reachable.
    jwt_secret_key: str = os.getenv("JWT_SECRET_KEY", "dev-only-insecure-secret-change-me")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = int(os.getenv("JWT_EXPIRE_MINUTES", str(60 * 24 * 7)))  # 7 days

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

# ---------------------------------------------------------------------------
# Risk / anomaly engine configuration
# ---------------------------------------------------------------------------
# Composite risk score weights (must sum to 1.0) — how much each dimension
# contributes to the overall 0-100 risk score in app/risk_engine.py.
RISK_WEIGHTS = {
    "satellite_discrepancy": 0.50,
    "financial": 0.20,
    "timeline": 0.15,
    "duplicate_work": 0.15,
}
