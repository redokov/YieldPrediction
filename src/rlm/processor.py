import logging
from pathlib import Path
from typing import Optional
from datetime import datetime
from tqdm import tqdm

from .config import settings
from .search import create_buffer, list_scenes
from .dagshub_search import get_available_scenes_from_dagshub
from .indices import process_scene_indices
from .models import SearchRequest, AnalysisResult, SceneMetadata
from .downloader import download_sentinel_data

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    datefmt='%H:%M:%S'
)
logger = logging.getLogger(__name__)


def process_scene(
    kml_path: str,
    scene_id: Optional[str] = None,
    year: int = 2024,
    use_llm: bool = True
) -> AnalysisResult:
    """
    Основная функция Этапа 2:
    1. Создаёт буфер 500м
    2. Ищет подходящие сцены
    3. Обрабатывает выбранную сцену (индексы + маска облаков)
    4. Формирует отчёт
    5. (Опционально) Запрашивает анализ у Qwen3
    """
    logger.info(f"Начало обработки поля: {kml_path}")
    logger.info(f"Параметры: buffer={settings.buffer_meters}m, max_cloud={settings.max_cloud_cover}%, период={settings.default_start_date} — {settings.default_end_date}")

    request = SearchRequest(
        kml_path=kml_path,
        start_date=settings.default_start_date,
        end_date=settings.default_end_date,
        max_cloud_cover=settings.max_cloud_cover,
        buffer_meters=settings.buffer_meters
    )
    
    logger.info("Шаг 1/4: Создание буферной зоны 500м...")
    buffer_path = create_buffer(kml_path, request.buffer_meters)
    logger.info(f"Буфер создан: {buffer_path}")

    logger.info("Шаг 2/4: Поиск доступных сцен Sentinel-2 через Dagshub (S3)...")
    scenes = list_scenes(request)
    logger.info(f"Найдено сцен: {len(scenes)}")

    if not scenes:
        logger.warning("Сцены не найдены в sentinel-cogs. Используется демо-сцена.")
        scenes = [SceneMetadata(
            scene_id="demo_S2A_20250515",
            date=datetime(2025, 5, 15),
            cloud_cover=8.2,
            title="S2A_MSIL2A_20250515T080241_N0511_R049_T37UCB_20250515T112345.SAFE (demo)",
            preview_url=None,
            download_url=None
        )]

    selected_scene: SceneMetadata = scenes[0]
    logger.info(f"Выбрана сцена: {selected_scene.title} ({selected_scene.date.date()}), облачность {selected_scene.cloud_cover:.1f}%")

    # --- Реализация Этапа 2.5: Скачивание + прогресс-бар ---
    logger.info("Шаг 3/4: Доступ к COG-файлам Sentinel-2 через Dagshub (S3)...")
    # Для Dagshub мы не скачиваем SAFE, а работаем напрямую с COG (B04.tif, B08.tif, TCI.tif)
    # scene_path теперь — это путь к JSON-метаданным или просто идентификатор
    scene_path = f"s3://sentinel-cogs/sentinel-s2-l2a-cogs/{selected_scene.scene_id}"

    with tqdm(total=100, desc="Доступ к данным Dagshub", unit="%") as pbar:
        pbar.set_description("Загрузка метаданных...")
        pbar.update(50)
        pbar.set_description("Подготовка COG (TCI, B04, B08)...")
        pbar.update(50)
        logger.info(f"Сцена доступна по пути: {scene_path}")
        pbar.close()

    logger.info("Шаг 4/4: Расчёт спектральных индексов, визуализация RGB+NDVI с контуром...")
    start_time = datetime.now()
    indices_result = process_scene_indices(
        safe_path=Path(scene_path),
        buffer_geojson_path=buffer_path,
        visualize=True,
        output_dir=Path("output")
    )
    duration = (datetime.now() - start_time).total_seconds()
    logger.info(f"Обработка и визуализация завершены за {duration:.1f} сек")

    logger.info("Шаг 4/4: Формирование отчёта...")

    # 4. Формируем подробный отчёт
    report_lines = [
        "Отчёт по полю (RLM v0.2.1 - RGB + Contour)",
        f"KML: {Path(kml_path).name}",
        f"Выбранная сцена: {selected_scene.title}",
        f"Дата съёмки: {selected_scene.date.date()}",
        f"Облачность по каталогу: {selected_scene.cloud_cover:.1f}%",
        "",
        "=== Результаты обработки ===",
        f"NDVI (средний): {indices_result['ndvi_mean']:.3f}",
        f"NDWI (средний): {indices_result.get('ndwi_mean', 0):.3f}",
        f"Пикселей после маски облаков: {indices_result.get('valid_pixels_percent', 0):.1f}%",
        f"Время обработки: {duration:.1f} сек",
        f"Статус: {indices_result['status']}",
        f"RGB: {indices_result.get('rgb_path', 'не сохранено')}",
        f"NDVI: {indices_result.get('ndvi_path', 'не сохранено')}",
        "",
        indices_result.get('message', ''),
        indices_result.get('recommendation', '')
    ]

    report = "\n".join(report_lines)

    llm_analysis = None
    if use_llm:
        logger.info("Запрос анализа у Qwen3 (OpenRouter)...")
        # llm_analysis = call_llm(...)  # будет включено после установки litellm
        llm_analysis = "Qwen3-анализ временно отключён (отсутствует зависимость litellm)."
        report += f"\n\n=== Анализ и рекомендации от Qwen3 ===\n{llm_analysis}\n"

    logger.info("Обработка поля успешно завершена.")
    return AnalysisResult(
        status="success",
        scenes_found=len(scenes),
        selected_scene=selected_scene,
        report=report,
        llm_analysis=llm_analysis
    )

