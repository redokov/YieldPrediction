import logging
from pathlib import Path
from datetime import datetime
from typing import List, Tuple
import fsspec
import json
import mgrs
from fastkml import kml
import geopandas as gpd

from .models import SceneMetadata, SearchRequest
from .config import settings

logger = logging.getLogger(__name__)

def read_kml_polygon_coords(kml_path: str):
    with open(kml_path, 'rb') as f:
        k = kml.KML()
        k.from_string(f.read())
    for feature in k.features():
        for placemark in feature.features():
            geom = placemark.geometry
            if geom and geom.geom_type == 'Polygon':
                return list(geom.exterior.coords)
    return None

def calculate_centroid(coords):
    lngs, lats = zip(*coords)
    return sum(lngs)/len(lngs), sum(lats)/len(lats)

def get_mgrs_tile(lon: float, lat: float) -> str:
    m = mgrs.MGRS()
    return m.toMGRS(lat, lon, MGRSPrecision=0)

def parse_mgrs_tile(mgrs_tile: str) -> Tuple[str, str]:
    return mgrs_tile[:2], mgrs_tile[2:]

def get_available_scenes_from_dagshub(kml_path: str, start_date: str, end_date: str, max_cloud: int = 30) -> List[SceneMetadata]:
    """Поиск сцен Sentinel-2 L2A COGs через новый бакет Element 84 (AWS Earth Search).
    Данные переехали из sentinel-cogs в e84-earth-search-sentinel-cogs.
    Используется STAC-подход через metadata JSON."""
    logger.info("Поиск сцен Sentinel-2 L2A через Element 84 (e84-earth-search-sentinel-cogs)")

    coords = read_kml_polygon_coords(kml_path)
    if not coords:
        logger.error("Не удалось прочитать координаты из KML")
        return []

    lon, lat = calculate_centroid(coords)
    mgrs_tile = get_mgrs_tile(lon, lat)
    zone, square = parse_mgrs_tile(mgrs_tile)
    logger.info(f"MGRS тайл для поля: {mgrs_tile} (зона={zone}, квадрат={square})")

    s3_fs = fsspec.filesystem('s3', anon=True)
    scenes = []

    year = int(start_date[:4])
    # Используем только указанный месяц из диапазона (start_date)
    month = int(start_date[5:7]) if len(start_date) >= 7 else 4

    for day in range(1, 32):
        date_str = f"{year}{month:02d}{day:02d}"
        folder_name = f"S2A_{zone}{square}_{date_str}_0_L2A"
        json_path = f"sentinel-s2-l2a-cogs/{zone}/{square[0]}/{square[1:]}/{year}/{month}/{folder_name}/{folder_name}.json"
        s3_full_path = f"s3://e84-earth-search-sentinel-cogs/{json_path}"

        try:
            with s3_fs.open(s3_full_path, 'rb') as f:
                meta = json.load(f)

            props = meta.get('properties', {})
            cloud_cover = props.get('eo:cloud_cover', 100.0)
            # Дополнительно проверяем покрытие сцены (если есть)
            coverage = props.get('s2:cloud_shadow_percentage', 100) + cloud_cover

            if cloud_cover <= max_cloud and coverage < 90:
                scene_date = datetime.strptime(date_str, "%Y%m%d")
                base_url = f"s3://e84-earth-search-sentinel-cogs/sentinel-s2-l2a-cogs/{zone}/{square[0]}/{square[1:]}/{year}/{m}/{folder_name}"
                scenes.append(SceneMetadata(
                    scene_id=folder_name,
                    date=scene_date,
                    cloud_cover=float(cloud_cover),
                    title=folder_name,
                    preview_url=props.get('links', [{}])[0].get('href'),
                    download_url=base_url
                ))
                logger.info(f"Найдена подходящая сцена: {folder_name} | cloud={cloud_cover:.1f}%")
        except FileNotFoundError:
            continue
        except Exception as e:
            logger.debug(f"Ошибка при чтении {s3_full_path}: {e}")

    scenes.sort(key=lambda x: x.cloud_cover)
    logger.info(f"Всего найдено подходящих малооблачных сцен: {len(scenes)}")
    return scenes