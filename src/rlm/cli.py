import typer
from typing import Optional, List
from datetime import datetime
from pathlib import Path

from .search import list_scenes, create_buffer
from .processor import process_scene
from .sentinel_filter import filter_pipeline
from .indices import process_scene_indices
from .models import SearchRequest, SceneMetadata
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
    """Поиск доступных спутниковых сцен (STAC API)"""
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
    for scene in scenes[:5]:
        typer.echo(
            f"{scene.date.date()} | Облачность: {scene.cloud_cover:.1f}% | ID: {scene.scene_id[:8]}..."
        )
    return scenes


@app.command()
def analyze(
    kml_path: str = typer.Argument(..., help="Путь к KML-файлу"),
    year: int = typer.Option(2024, help="Год анализа"),
    buffer: int = typer.Option(500, help="Буфер в метрах"),
    use_llm: bool = typer.Option(True, "--llm/--no-llm", help="Использовать Qwen3 анализ")
):
    """Полный анализ поля (один снимок + LLM)"""
    result = process_scene(kml_path=kml_path, year=year, use_llm=use_llm)
    typer.echo("\n" + "="*80)
    typer.echo(result.report)
    typer.echo("="*80)
    return result


@app.command()
def process(
    kml_path: str = typer.Argument(..., help="Путь к KML-файлу"),
    start_date: Optional[str] = typer.Option(None, help="Начальная дата (YYYY-MM-DD)"),
    end_date: Optional[str] = typer.Option(None, help="Конечная дата (YYYY-MM-DD)"),
    max_cloud: float = typer.Option(10.0, help="Макс. облачность над полем (%)"),
    buffer_meters: int = typer.Option(500, help="Буферная зона (м)"),
    output_dir: str = typer.Option("output", help="Директория для результатов"),
    no_interactive: bool = typer.Option(False, "--no-interactive", help="Без интерактивного выбора")
):
    """Интерактивный анализ поля"""
    import logging
    logger = logging.getLogger(__name__)

    typer.echo("\n" + "=" * 70)
    typer.echo("RLM Process - интерактивный анализ поля")
    typer.echo("=" * 70)
    typer.echo(f"KML: {kml_path}")

    # Step 1: date range
    if not start_date:
        start_date = typer.prompt("Начальная дата (YYYY-MM-DD)", default=settings.default_start_date)
    if not end_date:
        end_date = typer.prompt("Конечная дата (YYYY-MM-DD)", default=settings.default_end_date)
    typer.echo(f"   Период: {start_date} - {end_date}")
    typer.echo(f"   Облачность <= {max_cloud}% | Буфер: {buffer_meters}м")

    # Step 2: SCL filter
    typer.echo("\nШаг 1/4: SCL-фильтрация...")
    date_range = f"{start_date}/{end_date}"
    scenes = filter_pipeline(
        kml_path=kml_path,
        date_range=date_range,
        max_cloud_percent=max_cloud,
        max_scene_cloud_prefilter=90.0,
        max_check_items=50,
    )

    if not scenes:
        typer.echo("\nНет снимков, прошедших SCL-фильтрацию.")
        raise typer.Exit(code=1)

    # Step 3: display scenes
    typer.echo(f"\nНайдено {len(scenes)} снимков:")
    typer.echo("  # | Дата       | Облачн. | Сцена")
    typer.echo("  ---+-----------+---------+----------------------------------------")
    for i, s in enumerate(scenes, 1):
        typer.echo(f"  {i:>3} | {s['datetime'][:10]} | {s['cloud_cover_field']:>6.1f}% | {s['item_id'][:45]}")

    # Step 4: user selection
    if no_interactive:
        selected_indices = list(range(len(scenes)))
        typer.echo(f"\n  --no-interactive: выбрано все {len(scenes)}")
    else:
        typer.echo("\nВыберите даты (1,3,5 | 1-5 | all | 0 - выйти):")
        choice = typer.prompt("Ваш выбор", default="all")
        if choice in ("0", "skip"):
            raise typer.Exit(code=0)
        elif choice.lower() == "all":
            selected_indices = list(range(len(scenes)))
        else:
            idx_set = set()
            for part in choice.replace(" ", "").split(","):
                if not part: continue
                if "-" in part:
                    a, b = part.split("-", 1)
                    idx_set.update(range(int(a) - 1, int(b)))
                else:
                    idx_set.add(int(part) - 1)
            selected_indices = sorted(idx_set)

    if not selected_indices:
        raise typer.Exit(code=0)

    typer.echo(f"\n  Выбрано {len(selected_indices)} дат")

    # Step 5: buffer
    typer.echo("\nШаг 2/4: Создание буфера...")
    buffer_path = create_buffer(kml_path, buffer_meters)

    # Step 6: process
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    typer.echo("\nШаг 3/4: Генерация RGB + NDVI...")

    for idx in selected_indices:
        scene_dict = scenes[idx]
        typer.echo(f"  [{idx+1}/{len(scenes)}] {scene_dict['datetime'][:10]} | cloud={scene_dict['cloud_cover_field']:.1f}%")

        scene = SceneMetadata(
            scene_id=scene_dict["item_id"],
            date=datetime.fromisoformat(scene_dict["datetime"].replace("Z", "+00:00")),
            cloud_cover=scene_dict["cloud_cover_field"],
            title=scene_dict["item_id"],
            preview_url=None,
            download_url=scene_dict["assets"].get("visual"),
            assets=scene_dict["assets"],
        )

        try:
            indices_result = process_scene_indices(
                safe_path=scene,
                buffer_geojson_path=buffer_path,
                visualize=True,
                output_dir=out_dir,
            )
            results.append({"scene": scene, "result": indices_result})
            typer.echo(f"     status: {indices_result.get('status', '?')} | NDVI: {indices_result.get('ndvi_mean', 0):.3f}")
            rgb = indices_result.get("rgb_path", "-")
            ndvi = indices_result.get("ndvi_path", "-")
            if rgb and rgb != "не создан":
                typer.echo(f"     RGB: {rgb}")
            if ndvi and ndvi != "не создан":
                typer.echo(f"     NDVI: {ndvi}")
        except Exception as e:
            logger.error(f"Ошибка {scene.scene_id}: {e}")
            typer.echo(f"     Ошибка: {e}")

    # Summary
    typer.echo("\n" + "=" * 70)
    typer.echo("СВОДКА")
    typer.echo("=" * 70)
    typer.echo(f"  Найдено: {len(scenes)}")
    typer.echo(f"  Обработано: {len(results)}")
    for r in results:
        s = r["scene"]
        res = r["result"]
        typer.echo(f"  * {s.date.date()} | cloud={s.cloud_cover:.1f}% | NDVI={res.get('ndvi_mean', 0):.3f}")
    typer.echo("\nГотово!")
    return results


if __name__ == "__main__":
    app()
