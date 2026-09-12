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

    # Satellite mode: "demo" (default, uses local demo imagery, no external
    # credentials needed) or "real" (Sentinel-2 via Copernicus Data Space).
    satellite_mode: str = os.getenv("SATELLITE_MODE", "demo")
    satellite_provider: str = os.getenv("SATELLITE_PROVIDER", "planetary-computer")

    # Copernicus Data Space credentials (only required when satellite_mode=real).
    copernicus_client_id: str = os.getenv("COPERNICUS_CLIENT_ID", "")
    copernicus_client_secret: str = os.getenv("COPERNICUS_CLIENT_SECRET", "")
    copernicus_catalogue_url: str = os.getenv(
        "COPERNICUS_CATALOGUE_URL", "https://catalogue.dataspace.copernicus.eu/odata/v1"
    )
    copernicus_token_url: str = os.getenv(
        "COPERNICUS_TOKEN_URL",
        "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
    )
    max_cloud_percentage: float = float(os.getenv("MAX_CLOUD_PERCENTAGE", "20"))
    planetary_stac_url: str = os.getenv("PLANETARY_STAC_URL", "https://planetarycomputer.microsoft.com/api/stac/v1")
    planetary_sign_url: str = os.getenv("PLANETARY_SIGN_URL", "https://planetarycomputer.microsoft.com/api/sas/v1/sign")

    # Vision AI configuration (Default: gemini-3.5-flash-lite)
    ai_vision_provider: str = os.getenv("AI_VISION_PROVIDER", "gemini")
    ai_vision_model: str = os.getenv("AI_VISION_MODEL", "gemini-3.5-flash-lite")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    openai_api_key: str = os.getenv("OPENAI_API_KEY", "")

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
