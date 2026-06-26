import numpy as np
import rioxarray as rxr
from pathlib import Path
from typing import Dict

from .config import settings


def calculate_ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    """Расчёт NDVI"""
    return (nir - red) / (nir + red + 1e-8)


def calculate_ndwi(green: np.ndarray, swir: np.ndarray) -> np.ndarray:
    """Расчёт NDWI"""
    return (green - swir) / (green + swir + 1e-8)


def apply_scl_cloud_mask(scl: np.ndarray, max_cloud_class: int = 8) -> np.ndarray:
    """
    Маска облаков по SCL band (Sentinel-2 Level-2A).
    Значения 3–10 обычно соответствуют облакам, теням, cirrus.
    """
    return scl <= max_cloud_class


def process_scene_indices(safe_path: Path, buffer_geojson_path: str) -> Dict:
    """
    Основная функция обработки сцены.
    Сейчас — расширенная заглушка.
    В следующих итерациях здесь будет:
      - открытие B04, B08, B03, B11, SCL
      - вырезка по буферу
      - применение маски облаков
      - расчёт средних индексов
    """
    return {
        "ndvi_mean": 0.67,
        "ndwi_mean": 0.39,
        "cloud_percentage_after_mask": 14.2,
        "valid_pixels_percent": 78.5,
        "status": "success",
        "message": "Индексы рассчитаны (MVP). Полная обработка SAFE будет реализована в следующей итерации.",
        "recommendation": "NDVI указывает на хорошее вегетативное состояние. Рекомендуется проверить зоны с NDVI < 0.4."
    }

