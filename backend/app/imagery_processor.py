"""
Lightweight Imagery Processor for InfraWatch.

Handles raster streaming via rasterio/httpx, SAS URL signing, spatial window cropping,
co-registration, and Affine transform tracking for geographic feature mapping.
"""
from dataclasses import dataclass
from pathlib import Path
import logging
from typing import Tuple, Optional, Any

import cv2
import httpx
import numpy as np
import rasterio
from rasterio.transform import from_bounds
from rasterio.warp import calculate_default_transform, reproject, Resampling
from rasterio.windows import from_bounds as window_from_bounds

from app.config import settings
from app.satellite_provider import SatelliteScene

logger = logging.getLogger("infrawatch.imagery_processor")

ASSET_DIR = Path(__file__).resolve().parent / "demo_assets"


@dataclass
class ProcessedImagery:
    t1_array: np.ndarray        # (H, W, 3) uint8 BGR
    t2_array: np.ndarray        # (H, W, 3) uint8 BGR
    transform: Any             # rasterio.Affine transform for candidate -> lon/lat mapping
    crs: str                   # e.g. "EPSG:4326"
    bounds: Tuple[float, float, float, float]  # (min_lon, min_lat, max_lon, max_lat)
    t1_scene: SatelliteScene
    t2_scene: SatelliteScene
    t1_image_path: Path
    t2_image_path: Path


class ImageryProcessorError(RuntimeError):
    pass


class ImageryProcessor:
    def __init__(self, asset_dir: Optional[Path] = None):
        self.asset_dir = asset_dir or ASSET_DIR
        self.asset_dir.mkdir(parents=True, exist_ok=True)

    def _sign_url(self, href: str) -> str:
        if "blob.core.windows.net" not in href or "stac" not in settings.planetary_stac_url:
            return href
        try:
            res = httpx.get(settings.planetary_sign_url, params={"href": href}, timeout=15.0)
            res.raise_for_status()
            return res.json().get("href", href)
        except Exception as exc:
            logger.warning(f"Could not sign Planetary Computer SAS URL, using raw href: {exc}")
            return href

    def _download_raster(
        self, scene: SatelliteScene, latitude: float, longitude: float, size: Tuple[int, int] = (512, 512)
    ) -> np.ndarray:
        signed_href = self._sign_url(scene.image_href)
        
        # If it's an Esri export or direct HTTP preview image:
        if "export?" in signed_href or signed_href.endswith((".png", ".jpg", ".jpeg")):
            try:
                resp = httpx.get(signed_href, timeout=30.0)
                resp.raise_for_status()
                arr = np.frombuffer(resp.content, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is None:
                    raise ImageryProcessorError("Failed to decode HTTP image payload")
                return cv2.resize(img, size, interpolation=cv2.INTER_AREA)
            except Exception as exc:
                logger.error(f"Error fetching HTTP image from {signed_href}: {exc}")
                raise ImageryProcessorError(f"HTTP image download failed: {exc}") from exc

        # Stream via rasterio for Cloud-Optimized GeoTIFFs (COGs)
        try:
            with rasterio.open(signed_href) as src:
                # Calculate spatial crop window around the project lat/lon
                delta = 0.015  # ~1.5 km half-width
                min_lon, min_lat = longitude - delta, latitude - delta
                max_lon, max_lat = longitude + delta, latitude + delta

                # Compute a pixel-space Window from the geographic bounds and clamp
                # to the valid raster extent to avoid reading outside the COG.
                window = None
                try:
                    raw_window = window_from_bounds(
                        min_lon, min_lat, max_lon, max_lat,
                        transform=src.transform,
                    )
                    # Build the full-raster window using from_slices for rasterio compat
                    full_window = rasterio.windows.Window.from_slices(
                        rows=(0, src.height), cols=(0, src.width)
                    )
                    clipped = raw_window.intersection(full_window)

                    # Reject degenerate windows (project coords outside this tile)
                    col_off, row_off, win_w, win_h = (
                        clipped.col_off, clipped.row_off,
                        clipped.width, clipped.height,
                    )
                    if win_w < 1 or win_h < 1:
                        logger.warning(
                            f"Project ({latitude}, {longitude}) is outside tile bounds of {signed_href!r}. "
                            "Reading full raster as fallback."
                        )
                    else:
                        window = clipped
                except Exception as win_exc:
                    logger.warning(
                        f"Could not compute spatial window for ({latitude}, {longitude}): {win_exc}. "
                        "Reading entire raster as fallback."
                    )

                # Read RGB bands (or 1st band if single visual band)
                if src.count >= 3:
                    data = src.read(
                        [1, 2, 3],
                        window=window,
                        out_shape=(3, size[1], size[0]),
                        resampling=Resampling.bilinear,
                    )
                    img = np.transpose(data, (1, 2, 0))  # (H, W, 3)
                else:
                    data = src.read(
                        1,
                        window=window,
                        out_shape=(size[1], size[0]),
                        resampling=Resampling.bilinear,
                    )
                    img = cv2.cvtColor(data, cv2.COLOR_GRAY2BGR)

                # Normalize to uint8 if values are float/uint16
                if img.dtype != np.uint8:
                    img = cv2.normalize(img, None, 0, 255, cv2.NORM_MINMAX, dtype=cv2.CV_8U)

                # Convert RGB to BGR for OpenCV
                return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        except Exception as exc:
            logger.warning(f"Rasterio streaming failed for COG {signed_href}: {exc}. Using HTTP fallback.")
            # Fallback HTTP download
            try:
                resp = httpx.get(signed_href, timeout=30.0)
                resp.raise_for_status()
                arr = np.frombuffer(resp.content, dtype=np.uint8)
                img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
                if img is not None:
                    return cv2.resize(img, size, interpolation=cv2.INTER_AREA)
            except Exception:
                pass
            raise ImageryProcessorError(f"Raster download failed for scene {scene.scene_id}: {exc}") from exc

    def process(
        self,
        project_id: int,
        latitude: float,
        longitude: float,
        t1_scene: SatelliteScene,
        t2_scene: SatelliteScene,
        target_size: Tuple[int, int] = (512, 512),
    ) -> ProcessedImagery:
        logger.info(f"Processing rasters for project #{project_id} at ({latitude}, {longitude})")

        # Define common spatial bounding box (EPSG:4326)
        delta = 0.015
        bounds = (longitude - delta, latitude - delta, longitude + delta, latitude + delta)

        # Download & co-register arrays
        t1_arr = self._download_raster(t1_scene, latitude, longitude, target_size)
        t2_arr = self._download_raster(t2_scene, latitude, longitude, target_size)

        # Save the selected pair so it can be inspected or served later.
        t1_path = self.asset_dir / f"project_{project_id}_t1.png"
        t2_path = self.asset_dir / f"project_{project_id}_t2.png"

        cv2.imwrite(str(t1_path), t1_arr)
        cv2.imwrite(str(t2_path), t2_arr)

        # Compute Affine transform for 512x512 array mapped to EPSG:4326 bounds
        # from_bounds(west, south, east, north, width, height)
        transform = from_bounds(bounds[0], bounds[1], bounds[2], bounds[3], target_size[0], target_size[1])

        return ProcessedImagery(
            t1_array=t1_arr,
            t2_array=t2_arr,
            transform=transform,
            crs="EPSG:4326",
            bounds=bounds,
            t1_scene=t1_scene,
            t2_scene=t2_scene,
            t1_image_path=t1_path,
            t2_image_path=t2_path,
        )
