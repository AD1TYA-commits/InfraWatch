"""
Change GeoProcessor for InfraWatch.

Converts candidate pixel regions into valid GeoJSON EPSG:4326 FeatureCollections
using the raster Affine transform for Leaflet map overlay rendering.
"""
from typing import List, Dict, Any
import logging

import rasterio.transform

from app.change_detector import CVCandidate

logger = logging.getLogger("infrawatch.geo_processor")


class ChangeGeoProcessor:
    def candidates_to_geojson(
        self,
        candidates: List[CVCandidate],
        transform: Any,  # rasterio.Affine transform
        candidate_statuses: Dict[str, Dict[str, Any]] = None,
        detection_date: str = "",
    ) -> Dict[str, Any]:
        candidate_statuses = candidate_statuses or {}
        features: List[Dict[str, Any]] = []

        for cand in candidates:
            x, y, w, h = cand.bbox

            # Convert 4 pixel corners to (longitude, latitude) EPSG:4326 using affine transform
            # rasterio.transform.xy(transform, row, col) -> (x_coord/lon, y_coord/lat)
            top_left_lon, top_left_lat = rasterio.transform.xy(transform, y, x)
            top_right_lon, top_right_lat = rasterio.transform.xy(transform, y, x + w)
            bottom_right_lon, bottom_right_lat = rasterio.transform.xy(transform, y + h, x + w)
            bottom_left_lon, bottom_left_lat = rasterio.transform.xy(transform, y + h, x)

            polygon_coords = [
                [
                    [round(top_left_lon, 6), round(top_left_lat, 6)],
                    [round(top_right_lon, 6), round(top_right_lat, 6)],
                    [round(bottom_right_lon, 6), round(bottom_right_lat, 6)],
                    [round(bottom_left_lon, 6), round(bottom_left_lat, 6)],
                    [round(top_left_lon, 6), round(top_left_lat, 6)],  # Close polygon loop
                ]
            ]

            status_meta = candidate_statuses.get(cand.candidate_id, {})
            change_type = status_meta.get("change_type", "construction")
            ai_conf = status_meta.get("ai_confidence", cand.cv_confidence)

            feature = {
                "type": "Feature",
                "id": cand.candidate_id,
                "geometry": {
                    "type": "Polygon",
                    "coordinates": polygon_coords,
                },
                "properties": {
                    "candidate_id": cand.candidate_id,
                    "change_type": change_type,
                    "confidence": round(float(ai_conf), 2),
                    "cv_confidence": round(float(cand.cv_confidence), 2),
                    "ai_confidence": round(float(ai_conf), 2),
                    "estimated_area_m2": cand.estimated_area_m2,
                    "pixel_area": cand.pixel_area,
                    "detection_date": detection_date,
                    "label": "AI-derived change candidate",
                },
            }
            features.append(feature)

        geojson_collection = {
            "type": "FeatureCollection",
            "crs": {"type": "name", "properties": {"name": "urn:ogc:def:crs:OGC:1.3:CRS84"}},
            "features": features,
        }

        logger.info(f"Generated GeoJSON FeatureCollection with {len(features)} change polygon features.")
        return geojson_collection
