import os
from datetime import datetime
from typing import List
from sentinelsat import SentinelAPI, geojson_to_wkt
import geopandas as gpd

from .config import settings
from .models import SceneMetadata, SearchRequest
from .dagshub_search import get_available_scenes_from_dagshub


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
    """Поиск сцен Sentinel-2 через Dagshub (s3://sentinel-cogs) — без Copernicus"""
    import logging
    logger = logging.getLogger(__name__)

    logger.info("Создание буферной зоны 500м...")
    buffered_file = create_buffer(request.kml_path, request.buffer_meters)
    logger.info(f"Буфер сохранён: {buffered_file}")

    logger.info(f"Поиск малооблачных сцен за {request.start_date[:4]}-05 через Dagshub/S3...")
    scenes = get_available_scenes_from_dagshub(
        kml_path=request.kml_path,
        start_date=request.start_date,
        end_date=request.end_date,
        max_cloud=request.max_cloud_cover
    )

    if not scenes:
        logger.warning("Сцены не найдены в sentinel-cogs за указанный период.")
    else:
        logger.info(f"Найдено {len(scenes)} подходящих сцен (cloud ≤ {request.max_cloud_cover}%)")

    return scenes
