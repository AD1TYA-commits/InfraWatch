"""
Modular Satellite Imagery Providers for InfraWatch.

Supports Sentinel-2 L2A via Microsoft Planetary Computer STAC API with dynamic date range searching,
descending datetime sorting, cloud filtering, and Esri World Imagery fallback.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import logging
from typing import List, Optional, Tuple, Dict, Any

import httpx

from app.config import settings

logger = logging.getLogger("infrawatch.satellite_provider")


@dataclass
class SatelliteScene:
    scene_id: str
    acquisition_date: datetime
    cloud_percentage: float
    source: str
    image_href: str
    bbox: Tuple[float, float, float, float]  # [min_lon, min_lat, max_lon, max_lat]
    crs: str = "EPSG:4326"
    transform: Optional[List[float]] = None
    resolution: float = 10.0
    bands: List[str] = field(default_factory=lambda: ["visual"])

    def to_dict(self) -> Dict[str, Any]:
        return {
            "scene_id": self.scene_id,
            "acquisition_date": self.acquisition_date.isoformat(),
            "cloud_percentage": self.cloud_percentage,
            "source": self.source,
            "image_href": self.image_href,
            "bbox": list(self.bbox),
            "crs": self.crs,
            "resolution": self.resolution,
            "bands": self.bands,
        }


class SatelliteProviderError(RuntimeError):
    pass


class SatelliteProvider(ABC):
    @abstractmethod
    def find_scenes(
        self, latitude: float, longitude: float, start_date: datetime, end_date: datetime
    ) -> List[SatelliteScene]:
        pass

    @abstractmethod
    def get_scene_pair(
        self, latitude: float, longitude: float
    ) -> Tuple[SatelliteScene, SatelliteScene]:
        """Returns (T1_baseline, T2_observation) scene pair."""
        pass


class Sentinel2Provider(SatelliteProvider):
    def find_scenes(
        self, latitude: float, longitude: float, start_date: datetime, end_date: datetime
    ) -> List[SatelliteScene]:
        delta = 0.025  # ~2.5km box around project
        min_lon = longitude - delta
        max_lon = longitude + delta
        min_lat = latitude - delta
        max_lat = latitude + delta

        payload = {
            "collections": ["sentinel-2-l2a"],
            "bbox": [min_lon, min_lat, max_lon, max_lat],
            "datetime": f"{start_date.strftime('%Y-%m-%dT%H:%M:%SZ')}/{end_date.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            "query": {"eo:cloud_cover": {"lt": settings.max_cloud_percentage}},
            "limit": 100,
        }

        logger.info(
            f"Querying Planetary Computer STAC for lat={latitude}, lon={longitude}, range={start_date.date()}..{end_date.date()}"
        )
        try:
            response = httpx.post(f"{settings.planetary_stac_url}/search", json=payload, timeout=25.0)
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logger.error(f"STAC search API call failed: {exc}")
            raise SatelliteProviderError(f"STAC search request failed: {exc}") from exc

        scenes: List[SatelliteScene] = []
        for feature in data.get("features", []):
            props = feature.get("properties", {})
            assets = feature.get("assets", {})
            # Select best visual asset
            asset = assets.get("visual") or assets.get("rendered_preview")
            if not asset or not asset.get("href"):
                continue

            try:
                acq_dt = datetime.fromisoformat(props["datetime"].replace("Z", "+00:00"))
            except Exception:
                continue

            cloud_pct = float(props.get("eo:cloud_cover", 0.0))
            feat_bbox = feature.get("bbox", [min_lon, min_lat, max_lon, max_lat])

            scenes.append(
                SatelliteScene(
                    scene_id=feature["id"],
                    acquisition_date=acq_dt,
                    cloud_percentage=round(cloud_pct, 2),
                    source="sentinel-2-l2a-planetary-computer",
                    image_href=asset["href"],
                    bbox=(feat_bbox[0], feat_bbox[1], feat_bbox[2], feat_bbox[3]),
                    crs="EPSG:4326",
                    resolution=10.0,
                )
            )

        # Sort descending by acquisition datetime (newest first)
        scenes.sort(key=lambda s: s.acquisition_date, reverse=True)
        return scenes

    def get_scene_pair(
        self, latitude: float, longitude: float
    ) -> Tuple[SatelliteScene, SatelliteScene]:
        # Search dynamically up to current system date (2026+)
        now = datetime.now(timezone.utc)
        start_search = now - timedelta(days=730)  # Search past 2 years up to today

        scenes = self.find_scenes(latitude, longitude, start_search, now)
        if len(scenes) < 2:
            # Expand search range to 3 years
            scenes = self.find_scenes(latitude, longitude, now - timedelta(days=1095), now)

        if not scenes:
            raise SatelliteProviderError(f"No Sentinel-2 scenes found near lat={latitude}, lon={longitude}")

        # T2 = Newest suitable low-cloud observation
        t2 = scenes[0]

        # T1 = Older suitable baseline observation (at least 60 days older than T2 if available)
        t1_candidates = [s for s in scenes if (t2.acquisition_date - s.acquisition_date).days >= 60]
        if t1_candidates:
            t1 = t1_candidates[0]  # Take clearest recent baseline before T2
        elif len(scenes) > 1:
            t1 = scenes[-1]
        else:
            t1 = t2

        logger.info(
            f"Selected Sentinel-2 pair: T1={t1.scene_id} ({t1.acquisition_date.date()}, cloud={t1.cloud_percentage}%), T2={t2.scene_id} ({t2.acquisition_date.date()}, cloud={t2.cloud_percentage}%)"
        )
        return t1, t2


class EsriProvider(SatelliteProvider):
    """Fallback provider returning Esri World Imagery static export.

    WARNING: Esri World Imagery has no temporal depth — both T1 and T2 return
    the *same* image.  Callers must detect ``source == 'esri-world-imagery-fallback'``
    and skip change-detection / AI analysis to avoid false positives.
    """

    ESRI_FALLBACK_SOURCE = "esri-world-imagery-fallback"

    def find_scenes(
        self, latitude: float, longitude: float, start_date: datetime, end_date: datetime
    ) -> List[SatelliteScene]:
        now = datetime.now(timezone.utc)
        delta = 0.015
        bbox = (longitude - delta, latitude - delta, longitude + delta, latitude + delta)

        # Esri World Imagery is a static mosaic — there is only one timestamp.
        # We deliberately set T1 and T2 to the same URL and flag the source so
        # downstream code can honour the no-temporal-comparison rule.
        esri_url = (
            f"https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/export?"
            f"bbox={bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}&bboxSR=4326&imageSR=4326&size=512,512&f=image"
        )

        t2_date = now
        t1_date = now - timedelta(days=180)

        s2 = SatelliteScene(
            scene_id=f"esri-fallback-t2-{latitude:.4f}-{longitude:.4f}",
            acquisition_date=t2_date,
            cloud_percentage=0.0,
            source=self.ESRI_FALLBACK_SOURCE,
            image_href=esri_url,
            bbox=bbox,
            crs="EPSG:4326",
            resolution=2.0,
        )

        s1 = SatelliteScene(
            scene_id=f"esri-fallback-t1-{latitude:.4f}-{longitude:.4f}",
            acquisition_date=t1_date,
            cloud_percentage=0.0,
            source=self.ESRI_FALLBACK_SOURCE,
            image_href=esri_url,  # Same URL — no temporal depth available
            bbox=bbox,
            crs="EPSG:4326",
            resolution=2.0,
        )

        return [s2, s1]

    def get_scene_pair(
        self, latitude: float, longitude: float
    ) -> Tuple[SatelliteScene, SatelliteScene]:
        scenes = self.find_scenes(latitude, longitude, datetime.now(timezone.utc), datetime.now(timezone.utc))
        return scenes[1], scenes[0]  # (T1_baseline, T2_observation)
