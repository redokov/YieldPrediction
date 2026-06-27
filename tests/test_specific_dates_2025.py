"""
Test: process specific dates for test.kml (28 Aug - 10 Oct 2025).
"""
import sys; sys.path.insert(0, "src")
from pathlib import Path

def test_download_specific_dates():
    from src.rlm.sentinel_filter import filter_pipeline
    from src.rlm.search import create_buffer
    from src.rlm.config import settings
    from src.rlm.indices import process_scene_indices
    from src.rlm.models import SceneMetadata
    from datetime import datetime

    kml = "src/input/test.kml"
    target_dates = ["2025-08-31", "2025-09-25"]
    out_dir = Path("output")
    out_dir.mkdir(exist_ok=True)

    buffer_path = create_buffer(kml, settings.buffer_meters)
    print(f"Buffer: {buffer_path}")

    scenes = filter_pipeline(
        kml_path=kml,
        date_range="2025-08-28/2025-10-10",
        max_cloud_percent=30.0,
        max_scene_cloud_prefilter=90.0,
    )

    assert len(scenes) >= 1, f"Should find >= 1 scene, got {len(scenes)}"
    print(f"Found {len(scenes)} scenes")
    for s in scenes:
        print("  " + s["datetime"][:10] + " cloud=" + str(s["cloud_cover_field"]) + "%")

    target = [s for s in scenes if s["datetime"][:10] in target_dates]
    print(f"Target dates found: {len(target)}")
    assert len(target) >= 1, f"Should find >= 1 target date, got {len(target)}"

    for s in target:
        scene = SceneMetadata(
            scene_id=s["item_id"],
            date=datetime.fromisoformat(s["datetime"].replace("Z", "+00:00")),
            cloud_cover=s["cloud_cover_field"],
            title=s["item_id"],
            assets=s["assets"],
        )
        r = process_scene_indices(
            safe_path=scene,
            buffer_geojson_path=buffer_path,
            visualize=True,
            output_dir=out_dir,
        )
        print(f"  {s['datetime'][:10]}: status={r.get('status')}, NDVI={r.get('ndvi_mean', 0):.3f}")
        assert r.get("status") in ("success", "warning")
    print("\nTest PASSED!")
