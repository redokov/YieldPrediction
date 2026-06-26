import rasterio
import numpy as np
from shapely.geometry import Polygon
import geopandas as gpd

def calculate_indices(band_red, band_nir, band_green, band_swir):
    ndvi = (band_nir - band_red) / (band_nir + band_red + 1e-8)
    ndwi = (band_green - band_swir) / (band_green + band_swir + 1e-8)
    return ndvi, ndwi

def process_field_to_report(scene_path: str, kml_path: str) -> str:
    """Заглушка обработки сцены — будет расширена под реальные SAFE-архивы"""
    return f"""Отчёт по полю (KML: {kml_path})
Сцена: {scene_path}
Средний NDVI: 0.68
Средний NDWI: 0.41
Облачность: 12%
Зоны стресса: 18% площади
Рекомендуемая урожайность (прогноз): 4.8 т/га
"""
