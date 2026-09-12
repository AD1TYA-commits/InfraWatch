"""Sentinel-2 L2A scene preparation for the real-image comparison path."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

import cv2
import numpy as np
import rasterio

from app.services.demo_images import ASSET_DIR


class SceneProcessingError(RuntimeError):
    pass


def _band_member(archive: ZipFile, suffix: str) -> str:
    matches = [name for name in archive.namelist() if name.endswith(suffix)]
    if not matches:
        raise SceneProcessingError(f"Sentinel-2 archive has no {suffix} band.")
    return matches[0]


def _read_band(archive: ZipFile, suffix: str) -> np.ndarray:
    with rasterio.MemoryFile(archive.read(_band_member(archive, suffix))) as memory:
        with memory.open() as dataset:
            return dataset.read(1).astype(np.float32)


def _to_uint8(values: np.ndarray, low: float = 2, high: float = 98) -> np.ndarray:
    valid = values[np.isfinite(values)]
    if valid.size == 0:
        return np.zeros(values.shape, dtype=np.uint8)
    lo, hi = np.percentile(valid, (low, high))
    if hi <= lo:
        return np.zeros(values.shape, dtype=np.uint8)
    return np.clip((values - lo) * 255 / (hi - lo), 0, 255).astype(np.uint8)


def prepare_sentinel_scene(archive_bytes: bytes, asset_prefix: str) -> Path:
    """Extract a 10 m true-colour PNG from a downloaded Sentinel-2 product.

    The source archive is never published; only this derived, display-safe PNG
    is retained under the app's static demo-assets mount.
    """
    try:
        with ZipFile(BytesIO(archive_bytes)) as archive:
            red = _read_band(archive, "_B04_10m.jp2")
            green = _read_band(archive, "_B03_10m.jp2")
            blue = _read_band(archive, "_B02_10m.jp2")
    except Exception as exc:  # rasterio/zip errors are normal provider failures
        raise SceneProcessingError(f"Could not prepare Sentinel-2 true-colour image: {exc}") from exc
    image = cv2.merge([_to_uint8(blue), _to_uint8(green), _to_uint8(red)])
    # Keep browser payloads manageable while preserving enough construction detail.
    max_size = 1600
    height, width = image.shape[:2]
    if max(height, width) > max_size:
        scale = max_size / max(height, width)
        image = cv2.resize(image, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    path = ASSET_DIR / f"{asset_prefix}.png"
    if not cv2.imwrite(str(path), image):
        raise SceneProcessingError("Could not write prepared Sentinel-2 image.")
    return path


def prepare_preview_scene(image_bytes: bytes, asset_prefix: str) -> Path:
    """Validate and downsize an actual rendered Sentinel-2 image."""
    encoded = np.frombuffer(image_bytes, dtype=np.uint8)
    image = cv2.imdecode(encoded, cv2.IMREAD_COLOR)
    if image is None:
        raise SceneProcessingError("The provider response was not a readable satellite image.")
    height, width = image.shape[:2]
    max_size = 1600
    if max(height, width) > max_size:
        scale = max_size / max(height, width)
        image = cv2.resize(image, (int(width * scale), int(height * scale)), interpolation=cv2.INTER_AREA)
    ASSET_DIR.mkdir(parents=True, exist_ok=True)
    path = ASSET_DIR / f"{asset_prefix}.png"
    if not cv2.imwrite(str(path), image):
        raise SceneProcessingError("Could not write prepared satellite image.")
    return path
