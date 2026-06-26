import os
from pathlib import Path
from sentinelsat import SentinelAPI, geojson_to_wkt
import geopandas as gpd
from shapely.geometry import Polygon

def read_kml_to_geojson(kml_path: str) -> str:
    """Конвертирует KML в GeoJSON WKT для скачивания"""
    gdf = gpd.read_file(kml_path)
    if gdf.empty:
        raise ValueError("KML файл не содержит геометрий")
    return geojson_to_wkt(gdf.__geo_interface__)

def download_sentinel_data(kml_path: str, year: int = 2024, output_dir: str = "data") -> str:
    """Скачивает Sentinel-2 данные для поля (заглушка — будет дорабатываться)"""
    Path(output_dir).mkdir(exist_ok=True)
    
    api = SentinelAPI(
        os.getenv("COPERNICUS_USERNAME"),
        os.getenv("COPERNICUS_PASSWORD"),
        "https://apihub.copernicus.eu/apihub"
    )
    
    footprint = read_kml_to_geojson(kml_path)
    
    products = api.query(
        footprint,
        date=(f"{year}-04-01", f"{year}-09-30"),
        platformname="Sentinel-2",
        cloudcoverpercentage=(0, 30),
        processinglevel="Level-2A"
    )
    
    if not products:
        raise Exception("Не найдено подходящих сцен Sentinel-2")
    
    # Для MVP берём первую сцену
    product_id = list(products.keys())[0]
    api.download(product_id, directory_path=output_dir)
    
    scene_path = os.path.join(output_dir, f"{product_id}.SAFE")
    return scene_path
