"""Small Copernicus Data Space adapter used only when SATELLITE_MODE=real.

It deliberately keeps catalogue discovery separate from raster processing. That
makes the screening pipeline testable offline and prevents the demo mode from
ever silently calling an external satellite service.
"""
from dataclasses import dataclass
from datetime import date
from typing import Any

import httpx

from app.config import settings


class SatelliteProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class Scene:
    product_id: str
    name: str
    acquisition_date: str
    cloud_percentage: float | None
    download_url: str


class CopernicusClient:
    def _access_token(self) -> str:
        if not settings.copernicus_client_id or not settings.copernicus_client_secret:
            raise SatelliteProviderError(
                "COPERNICUS_CLIENT_ID and COPERNICUS_CLIENT_SECRET are required when SATELLITE_MODE=real."
            )
        response = httpx.post(
            settings.copernicus_token_url,
            data={
                "client_id": settings.copernicus_client_id,
                "client_secret": settings.copernicus_client_secret,
                "grant_type": "client_credentials",
            },
            timeout=30,
        )
        response.raise_for_status()
        token = response.json().get("access_token")
        if not token:
            raise SatelliteProviderError("Copernicus did not return an access token.")
        return token

    def find_scenes(self, latitude: float, longitude: float, start: date, end: date) -> list[Scene]:
        # A small AOI avoids requesting an entire district for a project-point screen.
        delta = 0.01
        polygon = (
            f"POLYGON(({longitude-delta} {latitude-delta},{longitude+delta} {latitude-delta},"
            f"{longitude+delta} {latitude+delta},{longitude-delta} {latitude+delta},"
            f"{longitude-delta} {latitude-delta}))"
        )
        filters = [
            "Collection/Name eq 'SENTINEL-2'",
            f"ContentDate/Start ge {start.isoformat()}T00:00:00.000Z",
            f"ContentDate/Start le {end.isoformat()}T23:59:59.999Z",
            f"OData.CSC.Intersects(area=geography'SRID=4326;{polygon}')",
        ]
        params: dict[str, Any] = {
            "$filter": " and ".join(filters),
            "$orderby": "ContentDate/Start asc",
            "$top": 100,
            "$expand": "Attributes",
        }
        response = httpx.get(f"{settings.copernicus_catalogue_url}/Products", params=params, timeout=30)
        response.raise_for_status()
        scenes: list[Scene] = []
        for product in response.json().get("value", []):
            attributes = {a.get("Name"): a.get("Value") for a in product.get("Attributes", [])}
            if attributes.get("productType") not in (None, "S2MSI2A"):
                continue
            cloud = attributes.get("cloudCover")
            cloud_value = float(cloud) if cloud is not None else None
            if cloud_value is not None and cloud_value > settings.max_cloud_percentage:
                continue
            product_id = str(product["Id"])
            scenes.append(Scene(
                product_id=product_id,
                name=product["Name"],
                acquisition_date=product["ContentDate"]["Start"],
                cloud_percentage=cloud_value,
                download_url=f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({product_id})/$value",
            ))
        return scenes

    def download_scene(self, scene: Scene) -> bytes:
        token = self._access_token()
        response = httpx.get(scene.download_url, headers={"Authorization": f"Bearer {token}"}, timeout=180)
        response.raise_for_status()
        return response.content
