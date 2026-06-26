import typer
from typing import Optional
from datetime import datetime

from .search import list_scenes, create_buffer
from .processor import process_scene
from .models import SearchRequest
from .config import settings

app = typer.Typer(name="rlm", help="Remote Learning & Monitoring Toolkit")


@app.command()
def search(
    kml_path: str = typer.Argument(..., help="Путь к KML-файлу"),
    start_date: Optional[str] = typer.Option(None, help="Начальная дата (YYYY-MM-DD)"),
    end_date: Optional[str] = typer.Option(None, help="Конечная дата (YYYY-MM-DD)"),
    max_cloud: int = typer.Option(30, help="Максимальная облачность (%)"),
    buffer: int = typer.Option(500, help="Буферная зона в метрах")
):
    """Поиск доступных спутниковых сцен"""
    if start_date is None:
        start_date = settings.default_start_date
    if end_date is None:
        end_date = settings.default_end_date

    request = SearchRequest(
        kml_path=kml_path,
        start_date=start_date,
        end_date=end_date,
        max_cloud_cover=max_cloud,
        buffer_meters=buffer
    )

    scenes = list_scenes(request)
    typer.echo(f"Найдено сцен: {len(scenes)}")
    for scene in scenes[:5]:  # показываем первые 5
        typer.echo(
            f"{scene.date.date()} | Облачность: {scene.cloud_cover:.1f}% | ID: {scene.scene_id[:8]}..."
        )
    return scenes


@app.command()
def analyze(
    kml_path: str = typer.Argument(..., help="Путь к KML-файлу"),
    year: int = typer.Option(2024, help="Год анализа"),
    buffer: int = typer.Option(500, help="Буфер в метрах")
):
    """Полный анализ поля"""
    result = process_scene(kml_path=kml_path, year=year)
    typer.echo(result.report)
    return result


if __name__ == "__main__":
    app()
