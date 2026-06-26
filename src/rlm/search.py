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
    """Поиск сцен Sentinel-2 L2A через STAC API (Earth Search by Element 84).
    Используется pystac-client + коллекция sentinel-2-l2a вместо ручного перебора JSON."""
    import logging
    from datetime import datetime
    from pystac_client import Client
    import geopandas as gpd
    from shapely.geometry import mapping, box

    logger = logging.getLogger(__name__)
    logger.info("Поиск сцен через STAC API (https://earth-search.aws.element84.com/v1)")

    # Читаем геометрию поля
    gdf = gpd.read_file(request.kml_path)
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    bbox = gdf.total_bounds.tolist()  # [minx, miny, maxx, maxy]

    client = Client.open("https://earth-search.aws.element84.com/v1")
    search = client.search(
        collections=["sentinel-2-l2a"],
        bbox=bbox,
        datetime=f"{request.start_date}/{request.end_date}",
        query={"eo:cloud_cover": {"lte": request.max_cloud_cover}},
        max_items=10,
        # sortby убрано, т.к. вызывает ошибку mapping на сервере
    )

    items = list(search.items())
    logger.info(f"Найдено {len(items)} сцен по STAC-запросу (cloud ≤ {request.max_cloud_cover}%)")

    scenes = []
    for item in items:
        props = item.properties
        scene_id = item.id
        date = datetime.fromisoformat(props["datetime"].replace("Z", "+00:00"))

        scenes.append(SceneMetadata(
            scene_id=scene_id,
            date=date,
            cloud_cover=float(props.get("eo:cloud_cover", 99.0)),
            title=scene_id,
            preview_url=item.assets.get("thumbnail", {}).href,
            download_url=item.self_href  # ссылка на метаданные, дальше берём asset
        ))
        logger.info(f"Найдена сцена: {scene_id} | cloud={props.get('eo:cloud_cover', 99.0):.1f}%")

    return scenes

    if not scenes:
        logger.warning("Сцены не найдены в sentinel-cogs за указанный период.")
    else:
        logger.info(f"Найдено {len(scenes)} подходящих сцен (cloud ≤ {request.max_cloud_cover}%)")

    return scenes
