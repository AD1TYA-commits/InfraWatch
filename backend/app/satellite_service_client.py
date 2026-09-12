"""
Thin HTTP client for the standalone `satellite-service` microservice
(https://github.com/... satellite-service, kept as its own separate project —
see its docs/04-integration.md). This is the ONLY file that knows the
satellite-service response shape; everything else in this backend keeps
working against InfraWatch's own AnalysisResultOut schema as before.
"""
from typing import Any, Dict

import httpx

from app.config import settings


class SatelliteServiceError(RuntimeError):
    pass


def run_pipeline(
    project_id: int,
    name: str,
    latitude: float,
    longitude: float,
    project_type: str,
    reported_progress: float,
) -> Dict[str, Any]:
    """Calls satellite-service's /pipeline/run (fetch real Sentinel-2 imagery,
    run the pretrained PlanAura change-detection model, narrate with Gemini or
    a template fallback) and returns its raw JSON response.

    Raises SatelliteServiceError only for transport failures (service down,
    timeout, bad HTTP status) — a normal "no imagery available" outcome comes
    back as a 200 response with an `error` field set, which callers should
    check for and handle, not treat as an exception.
    """
    try:
        resp = httpx.post(
            f"{settings.satellite_service_url}/pipeline/run",
            json={
                "project_id": str(project_id),
                "name": name,
                "latitude": latitude,
                "longitude": longitude,
                "project_type": project_type,
                "reported_progress": reported_progress,
            },
            timeout=90.0,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        raise SatelliteServiceError(f"satellite-service call failed: {exc}") from exc


def asset_url(relative_path: str) -> str:
    """satellite-service serves its data/ dir as static files at its own host —
    turn a path like 'data/T2/42/true_color.png' from its response into a full
    URL the frontend can hotlink directly."""
    if not relative_path:
        return ""
    return f"{settings.satellite_service_url}/{relative_path}"
