"""
Real satellite imagery retrieval helper for InfraWatch projects.

Routes through Sentinel2Provider and EsriProvider with dynamic date ranges (up to 2026+).
"""
import logging
from pathlib import Path
from datetime import datetime
from typing import Tuple

import cv2
import numpy as np

from app.satellite_provider import Sentinel2Provider, EsriProvider, SatelliteScene

ASSET_DIR = Path(__file__).resolve().parents[1] / "demo_assets"
logger = logging.getLogger(__name__)


def asset_paths(project_id: int) -> Tuple[Path, Path]:
    return ASSET_DIR / f"project_{project_id}_before.png", ASSET_DIR / f"project_{project_id}_after.png"


def fetch_real_satellite_pair(lat: float, lon: float) -> Tuple[np.ndarray, np.ndarray, datetime, datetime]:
    """Query dynamic Sentinel2Provider (or Esri fallback) up to present system date."""
    try:
        provider = Sentinel2Provider()
        t1_scene, t2_scene = provider.get_scene_pair(lat, lon)
    except Exception as exc:
        logger.warning(f"Sentinel2Provider search failed ({exc}). Falling back to EsriProvider.")
        provider = EsriProvider()
        t1_scene, t2_scene = provider.get_scene_pair(lat, lon)

    # Convert scenes to imagery using ImageryProcessor
    from app.imagery_processor import ImageryProcessor
    processor = ImageryProcessor(asset_dir=ASSET_DIR)
    processed = processor.process(
        project_id=9999,
        latitude=lat,
        longitude=lon,
        t1_scene=t1_scene,
        t2_scene=t2_scene,
    )

    return (
        processed.t1_array,
        processed.t2_array,
        t1_scene.acquisition_date,
        t2_scene.acquisition_date,
    )


def generate_demo_images(projects: list = None) -> None:
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    default_coords = [
        (1, 28.4744, 77.5040),
        (2, 28.4530, 77.5310),
        (3, 28.4901, 77.4870),
        (4, 28.4655, 77.5195),
        (5, 28.5012, 77.4995),
        (6, 28.4388, 77.5120),
    ]
    coords = default_coords[:projects] if isinstance(projects, int) else default_coords
    for pid, lat, lon in coords:
        before_path, after_path = asset_paths(pid)
        try:
            t1, t2, _, _ = fetch_real_satellite_pair(lat, lon)
            cv2.imwrite(str(before_path), t1)
            cv2.imwrite(str(after_path), t2)
        except Exception as exc:
            logger.error(f"Could not prepare demo images for project {pid}: {exc}")
