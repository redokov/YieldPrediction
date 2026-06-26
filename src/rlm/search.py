import os
from datetime import datetime
from typing import List
from sentinelsat import SentinelAPI, geojson_to_wkt
import geopandas as gpd

from .config import settings
from .models import SceneMetadata, SearchRequest


def create_buffer(kml_path: str, buffer_meters: int = None) -> str:
    """Создаёт буферную зону вокруг поля (по умолчанию 500м)"""
    if buffer_meters is None:
        buffer_meters = settings.buffer_meters

    gdf = gpd.read_file(kml_path)
    if gdf.empty:
        raise ValueError(f"Файл {kml_path} не содержит геометрии")

    # Перепроецируем в UTM для корректного буфера в метрах
    gdf = gdf.to_crs(gdf.estimate_utm_crs())
    gdf['geometry'] = gdf.geometry.buffer(buffer_meters)
    gdf = gdf.to_crs("EPSG:4326")  # обратно в WGS84

    buffered_path = kml_path.replace(".kml", f"_buffer_{buffer_meters}m.geojson")
    gdf.to_file(buffered_path, driver="GeoJSON")
    return buffered_path


def list_scenes(request: SearchRequest) -> List[SceneMetadata]:
    """Поиск доступных сцен Sentinel-2 Level-2A"""
    buffered_file = create_buffer(request.kml_path, request.buffer_meters)
    
    footprint = geojson_to_wkt(gpd.read_file(buffered_file).__geo_interface__)

    api = SentinelAPI(
        settings.copernicus_username,
        settings.copernicus_password,
        "https://apihub.copernicus.eu/apihub"
    )

    products = api.query(
        footprint,
        date=(request.start_date, request.end_date),
        platformname="Sentinel-2",
        cloudcoverpercentage=(0, request.max_cloud_cover),
        processinglevel="Level-2A"
    )

    scenes = []
    for pid, meta in products.items():
        scenes.append(SceneMetadata(
            scene_id=pid,
            date=meta["beginposition"],
            cloud_cover=meta["cloudcoverpercentage"],
            title=meta["title"],
            preview_url=meta.get("preview_url"),
            download_url=None
        ))

    # Сортируем по дате (новые сверху)
    scenes.sort(key=lambda x: x.date, reverse=True)
    return scenes
