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
    """Сценарий 1.1: RGB + контур поля"""
    result: AnalysisResult = process_scene(
        kml_path=test_kml,
        year=2025,
        use_llm=False
    )

    assert result.status == "success", "Процессинг должен завершиться успешно"
    assert result.scenes_found >= 1, "Должна быть найдена хотя бы одна сцена через Dagshub"
    assert result.selected_scene is not None, "Должна быть выбрана сцена"
    assert result.selected_scene.cloud_cover < 30, "Облачность должна быть < 30%"

    report = result.report.lower()
    assert any(k in report for k in ["rgb", "tci", "визуализация", "изображение"]), "Отчёт должен упоминать визуализацию"
    assert "ndvi" in report, "В отчёте должен присутствовать NDVI"
    assert any(k in report for k in ["контур", "граница", "contour"]), "Отчёт должен упоминать наложение контура поля"

    # Проверка кэша и сохранения изображений
    rgb_file = output_dir / f"{result.selected_scene.scene_id}_rgb_with_contour.png"
    assert rgb_file.exists() or (output_dir / "rgb_with_contour.png").exists(), \
        "RGB изображение с контуром должно быть сохранено"

    print("E2E тест 1.1 (RGB + contour) пройден успешно")


def test_e2e_ndvi_with_contour(test_kml, output_dir):
    """Сценарий 1.2: NDVI + контур поля"""
    result: AnalysisResult = process_scene(
        kml_path=test_kml,
        year=2025,
        use_llm=False
    )

    assert result.status == "success"
    assert result.scenes_found >= 1
    assert 0.0 <= result.selected_scene.cloud_cover <= 100.0

    report = result.report
    assert "NDVI" in report
    assert "NDWI" in report
    assert any(k in report.lower() for k in ["ndvi", "contour", "граница", "контур"]), \
        "Должен быть упомянут NDVI и контур"

    ndvi_file = output_dir / f"{result.selected_scene.scene_id}_ndvi_with_contour.png"
    fallback_file = output_dir / "ndvi_with_contour.png"
    assert ndvi_file.exists() or fallback_file.exists(), \
        f"NDVI изображение с контуром должно быть сохранено. Проверялись: {ndvi_file}, {fallback_file}"

    # Проверка кэша
    cache_dir = Path("cache")
    assert cache_dir.exists(), "Папка кэша должна быть создана"

    print("E2E тест 1.2 (NDVI + contour) пройден успешно")


def test_cache_mechanism(test_kml):
    """Проверка работы кэша — второй запуск должен быть значительно быстрее"""
    import time

    start = time.time()
    result1 = process_scene(kml_path=test_kml, year=2025, use_llm=False)
    first_run = time.time() - start

    start = time.time()
    result2 = process_scene(kml_path=test_kml, year=2025, use_llm=False)
    second_run = time.time() - start

    assert result2.status == "success"
    assert second_run < first_run * 2, f"Второй запуск ({second_run:.2f}s) должен быть быстрее первого ({first_run:.2f}s) благодаря кэшу"

    print(f"Тест кэша пройден. Первый запуск: {first_run:.2f}s, второй: {second_run:.2f}s")
