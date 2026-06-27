from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional, Dict


class FieldBoundary(BaseModel):
    """Границы поля"""
    kml_path: str
    buffer_meters: int = 500


class SceneMetadata(BaseModel):
    """Метаданные спутниковой сцены"""
    scene_id: str
    date: datetime
    cloud_cover: float
    preview_url: Optional[str] = None
    download_url: Optional[str] = None
    title: str
    assets: Optional[Dict[str, str]] = None


class SearchRequest(BaseModel):
    """Запрос на поиск сцен"""
    kml_path: str
    start_date: str
    end_date: str
    max_cloud_cover: int = 30
    buffer_meters: int = 500


class AnalysisResult(BaseModel):
    """Результат анализа"""
    status: str
    scenes_found: int
    selected_scene: Optional[SceneMetadata] = None
    report: str
    llm_analysis: Optional[str] = None
