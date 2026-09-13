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

    # Satellite mode: "demo" uses bundled image pairs; "real" queries
    # Sentinel-2 imagery through the configured STAC endpoint.
    satellite_mode: str = os.getenv("SATELLITE_MODE", "demo")
    satellite_provider: str = os.getenv("SATELLITE_PROVIDER", "planetary-computer")

    max_cloud_percentage: float = float(os.getenv("MAX_CLOUD_PERCENTAGE", "20"))
    planetary_stac_url: str = os.getenv("PLANETARY_STAC_URL", "https://planetarycomputer.microsoft.com/api/stac/v1")
    planetary_sign_url: str = os.getenv("PLANETARY_SIGN_URL", "https://planetarycomputer.microsoft.com/api/sas/v1/sign")

    # Standalone satellite-service microservice (separate repo/folder) — real
    # Sentinel-2 fetch + pretrained-model change detection. When SATELLITE_MODE
    # is "real", non-demo projects are analyzed by calling out to this service
    # instead of the in-process satellite_provider/change_detector pipeline.
    satellite_service_url: str = os.getenv("SATELLITE_SERVICE_URL", "http://localhost:8001")

    # Vision analysis
    ai_vision_provider: str = os.getenv("AI_VISION_PROVIDER", "gemini")
    ai_vision_model: str = os.getenv("AI_VISION_MODEL", "gemini-2.5-flash-lite")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")

    # Comma-separated browser origins permitted to call this API.
    cors_origins: str = os.getenv("CORS_ORIGINS", "http://localhost:3000")

    # AI Cost controls & Candidate extraction parameters
    ai_max_candidates: int = int(os.getenv("AI_MAX_CANDIDATES", "20"))
    ai_crop_size: int = int(os.getenv("AI_CROP_SIZE", "512"))
    ai_context_margin: int = int(os.getenv("AI_CONTEXT_MARGIN", "64"))
    ai_min_cv_confidence: float = float(os.getenv("AI_MIN_CV_CONFIDENCE", "0.50"))
    ai_enable_cache: bool = os.getenv("AI_ENABLE_CACHE", "true").lower() in ("true", "1", "yes")

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
