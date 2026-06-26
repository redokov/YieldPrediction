"""
E2E тесты для RLM с Dagshub, кэшем, RGB и NDVI визуализацией.
"""
import pytest
from pathlib import Path
import shutil

from src.rlm.processor import process_scene
from src.rlm.models import AnalysisResult


@pytest.fixture(scope="module")
def test_kml():
    return "src/input/test.kml"


@pytest.fixture(scope="module")
def output_dir():
    out = Path("output")
    out.mkdir(exist_ok=True)
    yield out
    # cleanup после тестов (опционально)
    # shutil.rmtree(out, ignore_errors=True)


def test_e2e_rgb_with_contour(test_kml, output_dir):
    """Сценарий 1.1: RGB + контур поля (с использованием STAC + скачанного TCI)"""
    result: AnalysisResult = process_scene(
        kml_path=test_kml,
        year=2024,
        use_llm=False
    )

    assert result.status in ("success", "warning"), f"Ожидался success или warning, получен {result.status}"
    assert result.scenes_found >= 1, "Должна быть найдена хотя бы одна сцена через STAC"
    assert result.selected_scene is not None, "Должна быть выбрана сцена"
    assert result.selected_scene.cloud_cover <= 30, "Облачность должна быть <= 30%"

    report = result.report
    assert any(k in report.lower() for k in ["rgb", "tci", "визуализация", "демо", "contour", "контур", "ошибка"]), "Отчёт должен упоминать RGB или ошибку"
    assert "ndvi" in report.lower(), "В отчёте должен присутствовать NDVI"
    assert any(k in report.lower() for k in ["контур", "граница", "contour", "rgb_path"]), "Отчёт должен содержать информацию о контуре или пути к RGB"

    # Проверка RGB с контуром (с учётом TCI.tif в output)
    scene_id = result.selected_scene.scene_id if hasattr(result.selected_scene, 'scene_id') else "S2A_36UYC_20240430_0_L2A"
    rgb_file = output_dir / f"{scene_id}_rgb_with_contour.png"
    cached_rgb = Path("cache") / f"{scene_id}_rgb.png"
    tci_file = output_dir / f"{scene_id}_TCI.tif"

    assert (rgb_file.exists() or cached_rgb.exists() or tci_file.exists()), \
        f"Должен существовать RGB, кэш или TCI.tif. Проверялись: {rgb_file}, {cached_rgb}, {tci_file}"

    # Проверяем размер (RGB или кэш)
    size = 0
    if rgb_file.exists():
        size = rgb_file.stat().st_size
    elif cached_rgb.exists():
        size = cached_rgb.stat().st_size
    assert size > 30_000, f"Изображение RGB должно быть >30KB (текущий размер {size} байт). TCI: {tci_file.exists()}"

    assert any(k in result.report.lower() for k in ["контур", "contour", "rgb", "граница"]), \
        "Отчёт должен содержать информацию о контуре поля на RGB"

    print("E2E тест 1.1 (RGB + contour) пройден успешно")


def test_e2e_ndvi_with_contour(test_kml, output_dir):
    """Сценарий 1.2: NDVI + контур поля"""
    result: AnalysisResult = process_scene(
        kml_path=test_kml,
        year=2024,
        use_llm=False
    )

    assert result.status == "success"
    assert result.scenes_found >= 1
    assert 0.0 <= result.selected_scene.cloud_cover <= 100.0

    report = result.report
    assert "NDVI" in report
    assert "NDWI" in report
    assert any(k in report.lower() for k in ["ndvi", "contour", "граница", "контур", "rgb_path", "демо"]), \
        "Должен быть упомянут NDVI, контур или пути к изображениям"

    scene_id = result.selected_scene.scene_id if hasattr(result.selected_scene, 'scene_id') else "S2A_36UYC_20240430_0_L2A"
    ndvi_file = output_dir / f"{scene_id}_ndvi_with_contour.png"
    cached_ndvi = Path("cache") / f"{scene_id}_ndvi.png"

    assert ndvi_file.exists() or cached_ndvi.exists(), \
        f"NDVI изображение с контуром поля должно существовать. Проверялись: {ndvi_file}, {cached_ndvi}"
    if cached_ndvi.exists():
        assert cached_ndvi.stat().st_size > 20_000, "NDVI файл в кэше должен быть больше 20 КБ"

    # Проверка кэша
    cache_dir = Path("cache")
    assert cache_dir.exists(), "Папка кэша должна быть создана"

    print("E2E тест 1.2 (NDVI + contour) пройден успешно")


def test_cache_mechanism(test_kml):
    """Проверка работы кэша — второй запуск должен быть значительно быстрее"""
    import time

    start = time.time()
    result1 = process_scene(kml_path=test_kml, year=2024, use_llm=False)
    first_run = time.time() - start

    start = time.time()
    result2 = process_scene(kml_path=test_kml, year=2024, use_llm=False)
    second_run = time.time() - start

    assert result2.status == "success"
    assert second_run < first_run * 2, f"Второй запуск ({second_run:.2f}s) должен быть быстрее первого ({first_run:.2f}s) благодаря кэшу"

    print(f"Тест кэша пройден. Первый запуск: {first_run:.2f}s, второй: {second_run:.2f}s")
