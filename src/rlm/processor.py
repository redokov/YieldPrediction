import json
from pathlib import Path
from typing import Optional

from .config import settings
from .search import create_buffer, list_scenes
from .indices import process_scene_indices
from .models import SearchRequest, AnalysisResult, SceneMetadata
# from .llm import call_llm   # temporarily disabled to avoid litellm dependency in tests


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
    request = SearchRequest(
        kml_path=kml_path,
        start_date=settings.default_start_date,
        end_date=settings.default_end_date,
        max_cloud_cover=settings.max_cloud_cover,
        buffer_meters=settings.buffer_meters
    )
    
    # 1. Поиск сцен
    scenes = list_scenes(request)
    if not scenes:
        return AnalysisResult(
            status="error",
            scenes_found=0,
            report="Не найдено подходящих сцен Sentinel-2 с заданными параметрами."
        )

    selected_scene: SceneMetadata = scenes[0]  # берём самую свежую

    # 2. Создаём буфер (если ещё не создан)
    buffer_path = create_buffer(kml_path, request.buffer_meters)

    # 3. Обработка индексов (пока MVP)
    indices_result = process_scene_indices(
        safe_path=Path("data") / f"{selected_scene.scene_id}.SAFE",
        buffer_geojson_path=buffer_path
    )

    # 4. Формируем отчёт
    report = f"""Отчёт по полю
KML: {kml_path}
Выбранная сцена: {selected_scene.title}
Дата: {selected_scene.date.date()}
Облачность: {selected_scene.cloud_cover:.1f}%

=== Рассчитанные индексы ===
NDVI (средний): {indices_result['ndvi_mean']:.3f}
NDWI (средний): {indices_result['ndwi_mean']:.3f}
Пикселей после маски облаков: {indices_result.get('valid_pixels_percent', 0):.1f}%
Статус: {indices_result['status']}
"""

    llm_analysis = None
    if use_llm:
        llm_analysis = "Анализ Qwen3 отключён в тестовой версии (litellm не установлен)."
        report += f"\n\n=== Анализ и рекомендации от Qwen3 ===\n{llm_analysis}"

    return AnalysisResult(
        status="success",
        scenes_found=len(scenes),
        selected_scene=selected_scene,
        report=report,
        llm_analysis=llm_analysis
    )

