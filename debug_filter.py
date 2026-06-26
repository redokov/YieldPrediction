"""Debug: проверить STAC search + bounding box + polygon containment"""
from pystac_client import Client
from shapely.geometry import mapping
from src.rlm.sentinel_filter import _load_field_polygon, _polygon_fully_within_bounds
import rasterio

poly = _load_field_polygon("src/input/test.kml")
print(f"Poly area={poly.area:.8f}, centroid=({poly.centroid.x:.4f}, {poly.centroid.y:.4f})")

client = Client.open("https://earth-search.aws.element84.com/v1")

# Short period for quick debug
for period in [("2024-05-01", "2024-05-15"), ("2024-06-01", "2024-06-30")]:
    print(f"\n--- Period: {period[0]} / {period[1]} ---")
    search = client.search(
        collections=["sentinel-2-l2a"],
        intersects=mapping(poly),
        datetime=f"{period[0]}/{period[1]}",
        query={"eo:cloud_cover": {"lte": 90}},
        max_items=5,
    )
    items = list(search.items())
    print(f"Items found: {len(items)}")
    for item in items:
        assets = item.assets
        vis_a = assets.get("visual")
        scl_a = assets.get("scl")
        dt = item.properties.get("datetime", "")[:10]
        cloud = item.properties.get("eo:cloud_cover", 99)
        print(f"  {item.id} | {dt} | scene_cloud={cloud}%")
        print(f"    visual: {'OK' if vis_a else 'NONE'}, scl: {'OK' if scl_a else 'NONE'}")
        if vis_a:
            try:
                with rasterio.open(vis_a.href) as src:
                    print(f"    CRS: {src.crs}, bounds: {src.bounds}")
                    ok = _polygon_fully_within_bounds(poly, src.bounds, src.crs)
                    print(f"    poly fully within: {ok}")
            except Exception as e:
                print(f"    ERROR opening visual: {e}")

print("\nDone.")