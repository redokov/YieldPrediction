"""
E2E тест: 5 снимков за 2025 год (по одному в каждый месяц: май–август + июнь для теста).
Поле: src/input/кур-кур-0012-8-2.kml
Для каждого снимка: RGB (TCI) + NDVI с контуром поля.
"""
import pytest
from pathlib import Path
from datetime import datetime


@pytest.fixture(scope="module")
def kml_path():
    return "src/input/кур-кур-0012-8-2.kml"


@pytest.fixture(scope="module")
def output_dir():
    out = Path("output")
    out.mkdir(exist_ok=True)
    yield out
    # cleanup после тестов (опционально)
    # shutil.rmtree(out, ignore_errors=True)


def test_one_per_month_2025(kml_path, output_dir):
    """
    Получить по одному лучшему снимку за каждый месяц 2025 года:
    май, июнь, июль, август.
    Для каждого: RGB + NDVI с контуром поля.
    """
    from src.rlm.sentinel_filter import filter_pipeline
    from src.rlm.search import create_buffer
    from src.rlm.config import settings
    from src.rlm.indices import process_scene_indices
    from src.rlm.models import SceneMetadata
    import logging

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    months = [
        (2025, 5, "май"),
        (2025, 6, "июнь"),
        (2025, 7, "июль"),
        (2025, 8, "август"),
    ]

    # Создаём буфер
    buffer_path = create_buffer(kml_path, settings.buffer_meters)
    logger.info(f"Буфер создан: {buffer_path}")

    results = []
    for year, month, month_name in months:
        start_date = f"{year}-{month:02d}-01"
        # Последний день месяца
        if month == 12:
            end_date = f"{year + 1}-01-01"
        else:
            end_date = f"{year}-{month + 1:02d}-01"

        logger.info(f"\n{'='*60}")
        logger.info(f"Месяц: {month_name} ({start_date} — {end_date})")
        logger.info(f"{'='*60}")

        # Фильтрация через filter_pipeline (SCL-проверка)
        scenes = filter_pipeline(
            kml_path=kml_path,
            date_range=f"{start_date}/{end_date}",
            max_cloud_percent=30.0,
            max_scene_cloud_prefilter=90.0,
            max_check_items=50,
        )

        if not scenes:
            logger.warning(f"  Нет снимков за {month_name}, прошедших фильтрацию")
            continue

        # Сортируем по облачности над полем
        scenes.sort(key=lambda x: x["cloud_cover_field"])

        # Берём лучший снимок
        best = scenes[0]
        logger.info(f"  Лучший снимок за {month_name}: {best['item_id']}")
        logger.info(f"    cloud_field={best['cloud_cover_field']:.1f}%")
        logger.info(f"    scene_cloud={best['cloud_cover_scene']:.1f}%")

        # Создаём SceneMetadata
        scene = SceneMetadata(
            scene_id=best["item_id"],
            date=datetime.fromisoformat(best["datetime"].replace("Z", "+00:00")),
            cloud_cover=best["cloud_cover_field"],
            title=best["item_id"],
            preview_url=None,
            download_url=best["assets"].get("visual"),
            assets=best["assets"],
        )

        # Обрабатываем: RGB + NDVI с контуром
        indices_result = process_scene_indices(
            safe_path=scene,
            buffer_geojson_path=buffer_path,
            visualize=True,
            output_dir=Path("output"),
        )

        # Собираем результат
        month_result = {
            "month": month_name,
            "scene_id": scene.scene_id,
            "date": scene.date.date(),
            "cloud_cover": scene.cloud_cover,
            "status": indices_result.get("status", "error"),
            "rgb_path": indices_result.get("rgb_path", "не создан"),
            "ndvi_path": indices_result.get("ndvi_path", "не создан"),
            "ndvi_mean": indices_result.get("ndvi_mean", 0.0),
        }
        results.append(month_result)

        rgb_size = Path(indices_result["rgb_path"]).stat().st_size if indices_result.get("rgb_path") and Path(indices_result["rgb_path"]).exists() else 0
        ndvi_size = Path(indices_result["ndvi_path"]).stat().st_size if indices_result.get("ndvi_path") and Path(indices_result["ndvi_path"]).exists() else 0

        logger.info(f"  Готово: RGB={rgb_size / 1024:.0f}KB, NDVI={ndvi_size / 1024:.0f}KB, NDVI_mean={month_result['ndvi_mean']:.3f}")

    # Проверки
    assert len(results) >= 1, f"Должна быть обработана хотя бы 1 сцена, получено {len(results)}"

    # Печать сводки
    logger.info(f"\n{'='*70}")
    logger.info("СВОДКА: снимки по месяцам 2025")
    logger.info(f"{'='*70}")
    for r in results:
        logger.info(
            f"  {r['month']:6s} | {r['date']} | cloud={r['cloud_cover']:.1f}% | "
            f"status={r['status']} | RGB={r['rgb_path']} | NDVI={r['ndvi_mean']:.3f}"
        )
    logger.info(f"{'='*70}")
    logger.info(f"Обработано сцен: {len(results)}")
    logger.info(f"{'='*70}")

    print(f"\nE2E тест 'один снимок за месяц 2025' пройден. Обработано {len(results)} сцен:")
    for r in results:
        print(f"  {r['month']:6s}: {r['scene_id']} | cloud={r['cloud_cover']:.1f}% | RGB={r['rgb_path']} | NDVI={r['ndvi_mean']:.3f}")
