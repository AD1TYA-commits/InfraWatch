"""Anonymous, real Sentinel-2 L2A access via Microsoft Planetary Computer.

The STAC catalogue and SAS signing service are public: no account, OAuth
client, or proprietary imagery SDK is needed for normal project-sized use.
"""
from dataclasses import dataclass
from datetime import date

import httpx

from app.config import settings


class PlanetaryComputerError(RuntimeError):
    pass


@dataclass(frozen=True)
class PlanetaryScene:
    item_id: str
    acquisition_date: str
    cloud_percentage: float | None
    image_href: str


class PlanetaryComputerClient:
    def find_scenes(self, latitude: float, longitude: float, start: date, end: date) -> list[PlanetaryScene]:
        delta = 0.01
        payload = {
            "collections": ["sentinel-2-l2a"],
            "bbox": [longitude - delta, latitude - delta, longitude + delta, latitude + delta],
            "datetime": f"{start.isoformat()}T00:00:00Z/{end.isoformat()}T23:59:59Z",
            "query": {"eo:cloud_cover": {"lt": settings.max_cloud_percentage}},
            "limit": 100,
        }
        response = httpx.post(f"{settings.planetary_stac_url}/search", json=payload, timeout=30)
        response.raise_for_status()
        scenes: list[PlanetaryScene] = []
        for feature in response.json().get("features", []):
            assets = feature.get("assets", {})
            # rendered_preview is a true-colour provider-generated image. visual
            # is a COG fallback for items without that convenient preview.
            asset = assets.get("rendered_preview") or assets.get("visual")
            if not asset or not asset.get("href"):
                continue
            props = feature.get("properties", {})
            scenes.append(PlanetaryScene(
                item_id=feature["id"], acquisition_date=props["datetime"],
                cloud_percentage=props.get("eo:cloud_cover"), image_href=asset["href"],
            ))
        return sorted(scenes, key=lambda item: item.acquisition_date)

    def download_preview(self, scene: PlanetaryScene) -> bytes:
        signed = httpx.get(settings.planetary_sign_url, params={"href": scene.image_href}, timeout=30)
        signed.raise_for_status()
        href = signed.json().get("href")
        if not href:
            raise PlanetaryComputerError("Planetary Computer did not return a signed asset URL.")
        image = httpx.get(href, timeout=120)
        image.raise_for_status()
        return image.content
