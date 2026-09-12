"""
Central configuration for InfraWatch backend.

All environment-driven settings live here. Risk-engine thresholds are kept
in one place (see RISK_THRESHOLDS below) per the project spec: no scattered,
unexplained magic numbers in the anomaly logic.
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

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

# ---------------------------------------------------------------------------
# Risk / anomaly engine configuration (Phase 2+, defined now so nothing here
# is an unexplained inline weight later).
# ---------------------------------------------------------------------------
RISK_THRESHOLDS = {
    # Percentage-point deviation between reported and observed progress.
    "deviation_watch": 15,     # >= 15 pts difference -> WATCH
    "deviation_high": 25,      # >= 25 pts difference -> HIGH
    "deviation_critical": 40,  # >= 40 pts difference -> CRITICAL
    # Days behind the expected milestone schedule.
    "schedule_slip_watch_days": 30,
    "schedule_slip_high_days": 90,
}
