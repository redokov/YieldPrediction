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
    """Новый поиск сцен через Dagshub / S3 sentinel-cogs (без Copernicus)"""
    logger.info("Поиск сцен через Dagshub (s3://sentinel-cogs)")

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

    # Ищем сцены за указанный период (май указанного года)
    year = int(start_date[:4])
    for month_day in range(1, 32):
        date_str = f"{year}05{month_day:02d}"
        folder_name = f"S2A_{zone}{square}_{date_str}_0_L2A"
        json_path = f"sentinel-s2-l2a-cogs/{zone}/{square[0]}/{square[1:]}/{year}/5/{folder_name}/{folder_name}.json"
        s3_full_path = f"s3://sentinel-cogs/{json_path}"

        try:
            with s3_fs.open(s3_full_path, 'rb') as f:
                meta = json.load(f)

            props = meta.get('properties', {})
            cloud_cover = props.get('eo:cloud_cover', 100.0)

            if cloud_cover <= max_cloud:
                scene_date = datetime.strptime(date_str, "%Y%m%d")
                scenes.append(SceneMetadata(
                    scene_id=folder_name,
                    date=scene_date,
                    cloud_cover=float(cloud_cover),
                    title=folder_name,
                    preview_url=props.get('links', [{}])[0].get('href'),
                    download_url=s3_full_path.replace('.json', '')
                ))
                logger.info(f"Найдена сцена: {folder_name} | cloud={cloud_cover:.1f}%")
        except FileNotFoundError:
            continue
        except Exception as e:
            logger.debug(f"Ошибка при чтении {s3_full_path}: {e}")

    scenes.sort(key=lambda x: x.date, reverse=True)
    logger.info(f"Всего найдено малооблачных сцен: {len(scenes)}")
    return scenes