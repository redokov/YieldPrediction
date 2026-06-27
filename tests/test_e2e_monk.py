"""E2E test: rlm process monk.kml Apr-Oct 2025."""
import sys; sys.path.insert(0, "src")
from pathlib import Path

def test_monk_pipeline():
    """Run full pipeline for monk.kml and verify no geometry errors."""
    from src.rlm.sentinel_filter import filter_pipeline
    from src.rlm.search import create_buffer
    from src.rlm.config import settings

    kml = "src/input/monk.kml"

    # Step 1: create_buffer must not fail
    bp = create_buffer(kml, settings.buffer_meters)
    assert Path(bp).exists(), f"Buffer not created: {bp}"
    print(f"OK: create_buffer -> {bp}")

    # Step 2: filter_pipeline must not fail (short period to keep test fast)
    scenes = filter_pipeline(
        kml_path=kml,
        date_range="2025-04-05/2025-04-06",
        max_cloud_percent=50.0,
        max_scene_cloud_prefilter=95.0,
    )
    assert isinstance(scenes, list), "filter_pipeline must return a list"
    print(f"OK: filter_pipeline -> {len(scenes)} scenes")

    for s in scenes:
        assert "item_id" in s
        assert "datetime" in s
        assert "cloud_cover_field" in s
    print("OK: all scene fields present")


def test_monk_cli_invocation():
    """Verify CLI command doesn't crash with geometry error."""
    from typer.testing import CliRunner
    from src.rlm.cli import app

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["process", "src/input/monk.kml",
         "--start-date", "2025-04-01",
         "--end-date", "2025-04-10",
         "--no-interactive",
         "--max-cloud", "50.0"],
        catch_exceptions=False,
    )
    print(f"CLI exit code: {result.exit_code}")
    if result.exit_code != 0:
        print(f"Output: {result.output[:500]}")
        # Exit code 1 is OK if no scenes passed filter (cloud issue)
        # But must NOT be ValueError about geometry
        assert "геометрии" not in str(result.exception or ""), \
            f"Geometry error: {result.exception}"
        assert "LIBKML" not in result.output, "LIBKML driver error should not appear"
