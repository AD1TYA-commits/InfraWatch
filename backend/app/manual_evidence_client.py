"""
HTTP client for satellite-service's /model/detect-images endpoint — the
manual-evidence counterpart to satellite_service_client.py. Used when a
project has no usable GPS coordinate and a contractor has instead supplied
before/after photos directly (see app/manual_evidence/ for stored files).
"""
from pathlib import Path
from typing import Any, Dict, Optional

import httpx

from app.config import settings


class ManualEvidenceError(RuntimeError):
    pass


def detect_images(
    before_path: Path,
    after_path: Path,
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> Dict[str, Any]:
    try:
        with open(before_path, "rb") as bf, open(after_path, "rb") as af:
            files = {
                "before": (before_path.name, bf, "application/octet-stream"),
                "after": (after_path.name, af, "application/octet-stream"),
            }
            data = {}
            if latitude is not None and longitude is not None:
                data = {"latitude": str(latitude), "longitude": str(longitude)}
            resp = httpx.post(
                f"{settings.satellite_service_url}/model/detect-images",
                files=files, data=data, timeout=60.0,
            )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        raise ManualEvidenceError(f"manual-evidence detection failed: {exc}") from exc
