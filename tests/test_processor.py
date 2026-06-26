import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path

from src.rlm.processor import process_scene
from src.rlm.search import create_buffer
from src.rlm.models import AnalysisResult
from src.rlm.config import settings


def test_create_buffer():
    """Тест создания буфера 500м"""
    test_kml = "src/input/test.kml"
    Path("tests/fixtures").mkdir(parents=True, exist_ok=True)

    buffered = create_buffer(test_kml, buffer_meters=500)
    
    assert Path(buffered).exists()
    assert "_buffer_500m.geojson" in buffered
    assert Path(buffered).stat().st_size > 100


@patch('src.rlm.search.list_scenes')
def test_process_scene(mock_list_scenes):
    """Тест обработки сцены с моками (без реального API Copernicus)"""
    mock_scene = MagicMock()
    mock_scene.scene_id = "S2A_MSIL2A_20240515T090123_N0500_R123_T37UCB_20240515T120000"
    mock_scene.title = "S2A_MSIL2A_20240515"
    mock_scene.date = "2025-05-15T10:00:00"
    mock_scene.cloud_cover = 8.5
    mock_list_scenes.return_value = [mock_scene]

    result: AnalysisResult = process_scene(
        kml_path="src/input/test.kml",
        use_llm=False
    )

    assert result.status == "success"
    assert result.scenes_found >= 1
    assert "NDVI" in result.report
    assert "Qwen3" not in result.report


def test_ndvi_range():
    """Алгоритмический тест: NDVI должен быть в диапазоне [-1, 1]"""
    from src.rlm.indices import calculate_ndvi
    import numpy as np

    red = np.array([0.2, 0.3, 0.1])
    nir = np.array([0.7, 0.6, 0.8])
    ndvi = calculate_ndvi(nir, red)
    
    assert ndvi.min() >= -1.0
    assert ndvi.max() <= 1.0
    assert ndvi.mean() > 0.5  # для вегетации
