"""
E2E тесты для периода апрель–октябрь 2025.
Поле: src/input/kur-kur-0012-8-2.geojson

Тест 1: показать доступные даты с SCL-фильтрацией
Тест 2: скачать по одному снимку за каждый месяц с RGB + NDVI
"""
import pytest
from pathlib import Path
from datetime import datetime

GEO_PATH = "src/input/kur-kur-0012-8-2.geojson"

# Месяцы для теста 2: апрель–октябрь 2025
MONTHS_2025 = [
    (2025, 4, "апр"),
    (2025, 5, "май"),
    (2025, 6, "июн"),
    (2025, 7, "июл"),
    (2025, 8, "авг"),
    (2025, 9, "сен"),
    (2025, 10, "окт"),
]


@pytest.fixture(scope="module")
def output_dir():
    out = Path("output")
    out.mkdir(exist_ok=True)
    yield out


def _end_of_month(year: int, month: int) -> str:
    """Возвращает последний день месяца в формате YYYY-MM-DD."""
    if month == 12:
        return f"{year + 1}-01-01"
    return f"{year}-{month + 1:02d}-01"


def test_show_available_dates_2025(caplog):
    """
    Тест 1: Показать доступные даты за апрель–октябрь 2025.
    Использует filter_pipeline() для двухэтапной SCL-фильтрации.
    """
    from src.rlm.sentinel_filter import filter_pipeline

    caplog.set_level(10)

    print("\n" + "=" * 70)
    print("ТЕСТ 1: Доступные даты апрель–октябрь 2025")
    print("=" * 70)
    print(f"Поле: {GEO_PATH}")

    all_scenes = filter_pipeline(
        kml_path=GEO_PATH,
        date_range="2025-04-01/2025-10-31",
        max_cloud_percent=30.0,
        max_scene_cloud_prefilter=90.0,
        max_check_items=50,
    )

    assert isinstance(all_scenes, list)
    print(f"Найдено сцен: {len(all_scenes)}")

    if all_scenes:
        all_scenes.sort(key=lambda x: x["datetime"])
        print(f"\n  {'Дата':<12} {'Облачность':>10} {'Сцена'}")
        print(f"  {'-'*12} {'-'*10} {'-'*50}")
        for s in all_scenes:
            print(f"  {s['datetime'][:10]:<12} {s['cloud_cover_field']:>7.1f}%   {s['item_id'][:48]}")

    # Сводка по месяцам
    print(f"\nСводка по месяцам:")
    for year, month, name in MONTHS_2025:
        month_scenes = [s for s in all_scenes if s["datetime"][:7] == f"{year}-{month:02d}"]
        if month_scenes:
            best = min(month_scenes, key=lambda x: x["cloud_cover_field"])
            print(f"  {name:4s}: {len(month_scenes)} сцен(ы), лучшая: {best['datetime'][:10]} "
                  f"(cloud={best['cloud_cover_field']:.1f}%)")
        else:
            print(f"  {name:4s}: нет сцен")

    print(f"\nИТОГО: {len(all_scenes)} сцен")
    assert len(all_scenes) >= 2, f"Должно быть >= 2 сцены, найдено {len(all_scenes)}"

    for s in all_scenes:
        assert "item_id" in s
        assert "datetime" in s
        assert "cloud_cover_field" in s
        assert "cloud_cover_scene" in s
        assert "nodata_percent" in s
        assert "assets" in s
        assert s["cloud_cover_field"] <= 30.0
        assert "visual" in s["assets"]


def test_download_one_per_month_2025(output_dir):
    """
    Тест 2: Скачать по одному лучшему снимку за каждый месяц апрель–октябрь 2025.
    Для каждого месяца: filter_pipeline -> лучшая сцена -> RGB + NDVI с контуром.
    """
    from src.rlm.sentinel_filter import filter_pipeline
    from src.rlm.search import create_buffer
    from src.rlm.config import settings
    from src.rlm.indices import process_scene_indices
    from src.rlm.models import SceneMetadata
    import logging

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)

    # Создаём буфер (один на все месяцы)
    buffer_path = create_buffer(GEO_PATH, settings.buffer_meters)
    print(f"\nБуфер создан: {buffer_path}")

    results = []

    for year, month, month_name in MONTHS_2025:
        start_date = f"{year}-{month:02d}-01"
        end_date = _end_of_month(year, month)

        print(f"\n{'='*60}")
        print(f"Месяц: {month_name} ({start_date} — {end_date})")
        print(f"{'='*60}")

        # Фильтрация через filter_pipeline (SCL-проверка)
        scenes = filter_pipeline(
            kml_path=GEO_PATH,
            date_range=f"{start_date}/{end_date}",
            max_cloud_percent=30.0,
            max_scene_cloud_prefilter=90.0,
            max_check_items=50,
        )

        if not scenes:
            print(f"  Нет снимков за {month_name}, прошедших фильтрацию")
            continue

        # Сортируем по облачности над полем, берём лучший
        scenes.sort(key=lambda x: x["cloud_cover_field"])
        best = scenes[0]
        print(f"  Лучший снимок: {best['item_id']}")
        print(f"    cloud_field={best['cloud_cover_field']:.1f}%")
        print(f"    nodata={best['nodata_percent']}%")

        scene = SceneMetadata(
            scene_id=best["item_id"],
            date=datetime.fromisoformat(best["datetime"].replace("Z", "+00:00")),
            cloud_cover=best["cloud_cover_field"],
            title=best["item_id"],
            preview_url=None,
            download_url=best["assets"].get("visual"),
            assets=best["assets"],
        )

        indices_result = process_scene_indices(
            safe_path=scene,
            buffer_geojson_path=buffer_path,
            visualize=True,
            output_dir=output_dir,
        )

        status = indices_result.get("status", "error")
        rgb_path = indices_result.get("rgb_path", "не создан")
        ndvi_path = indices_result.get("ndvi_path", "не создан")
        ndvi_mean = indices_result.get("ndvi_mean", 0.0)

        month_result = {
            "month": month_name,
            "scene_id": scene.scene_id,
            "date": scene.date.date(),
            "cloud_cover": scene.cloud_cover,
            "status": status,
            "rgb_path": rgb_path,
            "ndvi_path": ndvi_path,
            "ndvi_mean": ndvi_mean,
        }
        results.append(month_result)

        # Проверяем файлы
        rgb_size = 0
        ndvi_size = 0
        if rgb_path and Path(rgb_path).exists():
            rgb_size = Path(rgb_path).stat().st_size
        if ndvi_path and Path(ndvi_path).exists():
            ndvi_size = Path(ndvi_path).stat().st_size

        # Fallback на кэш
        if rgb_size == 0:
            cached_rgb = Path("cache") / f"{scene.scene_id}_rgb.png"
            if cached_rgb.exists():
                rgb_size = cached_rgb.stat().st_size
                rgb_path = str(cached_rgb)
        if ndvi_size == 0:
            cached_ndvi = Path("cache") / f"{scene.scene_id}_ndvi.png"
            if cached_ndvi.exists():
                ndvi_size = cached_ndvi.stat().st_size
                ndvi_path = str(cached_ndvi)

        assert rgb_size > 10_000, f"RGB для {month_name} мал: {rgb_size} байт"
        assert ndvi_size > 10_000, f"NDVI для {month_name} мал: {ndvi_size} байт"

        print(f"  Готово: RGB={rgb_size/1024:.0f}KB, NDVI={ndvi_size/1024:.0f}KB, "
              f"NDVI={ndvi_mean:.3f}, status={status}")

    assert len(results) >= 3, (
        f"Должно быть обработано >= 3 месяца, получено {len(results)}"
    )

    print(f"\n{'='*70}")
    print("СВОДКА апрель–октябрь 2025")
    print(f"{'='*70}")
    for r in results:
        print(f"  {r['month']:4s} | {r['date']} | cloud={r['cloud_cover']:.1f}% | "
              f"status={r['status']} | NDVI={r['ndvi_mean']:.3f}")
    print(f"{'='*70}")
    print(f"Обработано: {len(results)} из 7 месяцев")
    print(f"{'='*70}")
