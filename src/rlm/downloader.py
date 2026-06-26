import os
from pathlib import Path
# from sentinelsat import SentinelAPI, geojson_to_wkt  # больше не используем
import geopandas as gpd
from shapely.geometry import Polygon

from .config import settings

def read_kml_to_geojson(kml_path: str) -> str:
    """Конвертирует KML в GeoJSON WKT для скачивания"""
    gdf = gpd.read_file(kml_path)
    if gdf.empty:
        raise ValueError("KML файл не содержит геометрий")
    return geojson_to_wkt(gdf.__geo_interface__)

def download_sentinel_data(kml_path: str, year: int = 2025, output_dir: str = "data") -> str:
    """Скачивает Sentinel-2 Level-2A сцену для указанной области (KML)"""
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Запуск скачивания для года {year}, выходная папка: {output_dir}")

    Path(output_dir).mkdir(parents=True, exist_ok=True)
    
    api = SentinelAPI(
        os.getenv("COPERNICUS_USERNAME") or settings.copernicus_username,
        os.getenv("COPERNICUS_PASSWORD") or settings.copernicus_password,
        "https://apihub.copernicus.eu/apihub"
    )
    
    footprint = read_kml_to_geojson(kml_path)
    logger.info("Запрос к каталогу Sentinel-2 (может занять время)...")
    
    products = api.query(
        footprint,
        date=(f"{year}0501", f"{year}0531"),  # формат YYYYMMDD для sentinelsat
        platformname="Sentinel-2",
        cloudcoverpercentage=(0, 30),
        processinglevel="Level-2A"
    )
    
    if not products:
        raise Exception(f"Не найдено сцен Sentinel-2 Level-2A за май {year} с cloud < 30%")
    
    # Берём сцену с наименьшей облачностью
    sorted_products = sorted(products.items(), key=lambda x: x[1]["cloudcoverpercentage"])
    product_id, meta = sorted_products[0]
    
    logger.info(f"Начинается скачивание сцены: {meta['title']} (cloud={meta['cloudcoverpercentage']:.1f}%)")
    api.download(product_id, directory_path=output_dir, checksum=True)
    
    scene_path = str(Path(output_dir) / f"{product_id}.SAFE")
    logger.info(f"Скачивание завершено: {scene_path}")
    return scene_path
