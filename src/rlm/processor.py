from .config import settings
from .search import create_buffer
from .models import SearchRequest, AnalysisResult


def process_scene(kml_path: str, scene_id: str = None, year: int = 2024) -> AnalysisResult:
    """Основная обработка сцены (заглушка — будет расширена)"""
    request = SearchRequest(
        kml_path=kml_path,
        start_date=settings.default_start_date,
        end_date=settings.default_end_date,
        max_cloud_cover=settings.max_cloud_cover,
        buffer_meters=settings.buffer_meters
    )
    
    # Пока возвращаем минимальный результат
    return AnalysisResult(
        status="success",
        scenes_found=1,
        report=f"Буфер 500м создан. Сцена обработана (заглушка).\n"
               f"Buffer: {settings.buffer_meters}m | Max cloud: {settings.max_cloud_cover}%",
        llm_analysis=None
    )
