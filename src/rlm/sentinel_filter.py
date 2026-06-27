"""
Двухэтапная фильтрация снимков Sentinel-2 L2A.

Этап 1 — Грубая фильтрация через STAC API (intersects + cloud pre-filter).
Этап 2 — Точная пиксельная проверка: покрытие поля + nodata + облачность по SCL.

Использует COG (Cloud Optimized GeoTIFF) — rasterio читает только window
вокруг поля через HTTP Range Requests, без скачивания целых файлов.
"""

import logging
from typing import List, Dict, Optional, Tuple

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.windows import Window
from rasterio.features import geometry_mask
from pyproj import Transformer
from pystac_client import Client
from .search import read_geometry_file
from shapely.geometry import Polygon, MultiPolygon, mapping, box

logger = logging.getLogger(__name__)

# Классы SCL, относящиеся к облакам
CLOUD_SCL_CLASSES = {8, 9, 10, 3}  # 8=Cloud medium, 9=Cloud high, 10=Thin cirrus, 3=Cloud shadows

# STAC API endpoint
STAC_API_URL = "https://earth-search.aws.element84.com/v1"


def _load_field_polygon(kml_path: str) -> Polygon:
    """Загружает полигон поля из KML, возвращает в EPSG:4326."""
    gdf = read_geometry_file(kml_path)
    if gdf.empty:
        raise ValueError(f"KML {kml_path} не содержит геометрии")
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")

    geom = gdf.geometry.iloc[0]
    if geom.geom_type == "MultiPolygon":
        geom = max(geom.geoms, key=lambda g: g.area)
    return geom


def _project_polygon(polygon: Polygon, dst_crs) -> Polygon:
    """Перепроецирует полигон из EPSG:4326 в dst_crs."""
    transformer = Transformer.from_crs("EPSG:4326", dst_crs, always_xy=True)
    if polygon.geom_type == "MultiPolygon":
        polys = []
        for p in polygon.geoms:
            coords = [transformer.transform(x, y) for x, y in p.exterior.coords]
            polys.append(Polygon(coords))
        return MultiPolygon(polys)
    coords = [transformer.transform(x, y) for x, y in polygon.exterior.coords]
    return Polygon(coords)


def _polygon_fully_within_bounds(polygon_4326: Polygon, src_bounds, src_crs) -> bool:
    """Проверяет, что полигон ПОЛНОСТЬЮ попадает в bounds снимка."""
    polygon_proj = _project_polygon(polygon_4326, src_crs)
    scene_box = box(*src_bounds)
    return scene_box.contains(polygon_proj)


def _read_field_window(src_url: str, polygon_4326: Polygon, band: int = 1) -> Tuple[np.ndarray, rasterio.Affine, Polygon]:
    """
    Читает bounding box поля из COG и возвращает:
    (data, transform, polygon_in_src_crs).
    Использует Windowed read — только нужные пиксели.
    """
    with rasterio.open(src_url) as src:
        polygon_proj = _project_polygon(polygon_4326, src.crs)
        minx, miny, maxx, maxy = polygon_proj.bounds

        # Пиксельные координаты bbox
        row1, col1 = src.index(minx, maxy)
        row2, col2 = src.index(maxx, miny)
        row_start, row_stop = min(row1, row2), max(row1, row2) + 1
        col_start, col_stop = min(col1, col2), max(col1, col2) + 1

        # Ограничиваем размерами снимка
        row_start = max(0, row_start)
        col_start = max(0, col_start)
        row_stop = min(src.height, row_stop)
        col_stop = min(src.width, col_stop)

        window = Window.from_slices((row_start, row_stop), (col_start, col_stop))
        data = src.read(band, window=window, boundless=False)
        transform = src.window_transform(window)
        return data, transform, polygon_proj


def _check_nodata_inside_polygon(src_url: str, polygon_4326: Polygon) -> float:
    """
    Читает пиксели внутри полигона и возвращает долю nodata.
    Sentinel-2 L2A: nodata = 0.
    """
    data, transform, polygon_proj = _read_field_window(src_url, polygon_4326, band=1)
    if data.size == 0:
        return 1.0

    mask = geometry_mask(
        [mapping(polygon_proj)], transform=transform, invert=True, out_shape=data.shape
    )
    field_pixels = data[mask]
    if field_pixels.size == 0:
        return 1.0

    nodata_pixels = np.sum(field_pixels == 0)
    return nodata_pixels / field_pixels.size


def _check_cloud_over_field(scl_url: str, polygon_4326: Polygon) -> float:
    """
    Читает SCL-слой в области поля и возвращает процент облачных пикселей
    только по валидным (не nodata) пикселям внутри полигона.
    """
    data, transform, polygon_proj = _read_field_window(scl_url, polygon_4326, band=1)
    if data.size == 0:
        return 100.0

    mask = geometry_mask(
        [mapping(polygon_proj)], transform=transform, invert=True, out_shape=data.shape
    )
    field_pixels = data[mask]
    if field_pixels.size == 0:
        return 100.0

    valid = field_pixels > 0
    valid_count = np.count_nonzero(valid)
    if valid_count == 0:
        return 100.0

    cloud_count = np.count_nonzero(np.isin(field_pixels[valid], list(CLOUD_SCL_CLASSES)))
    return cloud_count / valid_count * 100


def filter_pipeline(
    kml_path: str,
    date_range: str = "2022-01-01/2025-12-31",
    max_cloud_percent: float = 10.0,
    max_scene_cloud_prefilter: float = 90.0,
    max_check_items: Optional[int] = None,
) -> List[Dict]:
    """
    Двухэтапная фильтрация снимков Sentinel-2 L2A.

    Параметры
    ---------
    kml_path : str
        Путь к KML-файлу с полигоном поля.
    date_range : str
        Диапазон дат в формате "YYYY-MM-DD/YYYY-MM-DD".
    max_cloud_percent : float
        Максимально допустимый процент облачности над полем (по SCL).
    max_scene_cloud_prefilter : float
        Предварительный фильтр по общей облачности сцены.
    max_check_items : int | None
        Максимальное количество снимков для точной проверки.
        Полезно для тестов и ускорения.

    Возвращает
    ----------
    List[Dict] — список прошедших фильтрацию снимков.
    """
    logger.info("=" * 60)
    logger.info("Запуск filter_pipeline")
    logger.info(f"  KML: {kml_path}")
    logger.info(f"  Период: {date_range}")
    logger.info(f"  Порог облачности над полем: {max_cloud_percent}%")
    logger.info(f"  Предфильтр общей облачности: {max_scene_cloud_prefilter}%")
    if max_check_items:
        logger.info(f"  Лимит проверяемых снимков: {max_check_items}")
    logger.info("=" * 60)

    # ── Этап 1: STAC-поиск ──
    logger.info("Этап 1: Поиск сцен через STAC API (intersects)...")

    field_polygon = _load_field_polygon(kml_path)
    logger.info(
        f"  Полигон поля: {field_polygon.area:.6f} кв.град, "
        f"центр ~({field_polygon.centroid.x:.4f}, {field_polygon.centroid.y:.4f})"
    )

    client = Client.open(STAC_API_URL)
    search = client.search(
        collections=["sentinel-2-l2a"],
        intersects=mapping(field_polygon),
        datetime=date_range,
        query={"eo:cloud_cover": {"lte": max_scene_cloud_prefilter}},
        max_items=None,
    )

    items = list(search.items())
    logger.info(
        f"  Найдено снимков (общая облачность ≤ {max_scene_cloud_prefilter}%): {len(items)}"
    )

    if not items:
        logger.warning("Снимки не найдены. Проверьте период и геометрию поля.")
        return []

    # ── Этап 2: Пиксельная проверка ──
    logger.info(f"Этап 2: Пиксельная проверка снимков...")
    logger.info(
        f"  Критерии: покрытие 100%, nodata=0%, облачность над полем ≤ {max_cloud_percent}%"
    )

    passed = []
    total = min(len(items), max_check_items) if max_check_items else len(items)

    for i, item in enumerate(items):
        if max_check_items and i >= max_check_items:
            logger.info(f"Достигнут лимит проверки max_check_items={max_check_items}")
            break

        item_id = item.id
        props = item.properties
        date_str = props.get("datetime", "")
        scene_cloud = float(props.get("eo:cloud_cover", 99.0))

        status_prefix = f"  [{i+1:3d}/{total}] {item_id} | {date_str[:10]} | scene_cloud={scene_cloud:.0f}%"

        assets = item.assets
        visual_asset = assets.get("visual")
        visual_href = visual_asset.href if visual_asset else None
        scl_asset = assets.get("scl")
        scl_href = scl_asset.href if scl_asset else None
        b04_asset = assets.get("B04") or assets.get("red")
        b04_href = b04_asset.href if b04_asset else None

        if not visual_href or not scl_href:
            logger.info(f"{status_prefix} → ОТБРАКОВАНО: отсутствуют visual или scl ассеты")
            continue

        try:
            # A. Проверка полного покрытия
            with rasterio.open(visual_href) as vis_src:
                vis_bounds = vis_src.bounds
                vis_crs = vis_src.crs

            if not _polygon_fully_within_bounds(field_polygon, vis_bounds, vis_crs):
                logger.info(f"{status_prefix} → ОТБРАКОВАНО: поле не полностью в bounds снимка")
                continue

            # B. Проверка nodata внутри поля
            nodata_band_url = b04_href if b04_href else visual_href
            nodata_pct = _check_nodata_inside_polygon(nodata_band_url, field_polygon)
            if nodata_pct > 0:
                logger.info(f"{status_prefix} → ОТБРАКОВАНО: nodata={nodata_pct:.1%} внутри поля")
                continue

            # C. Проверка облачности над полем по SCL
            cloud_pct = _check_cloud_over_field(scl_href, field_polygon)
            if cloud_pct > max_cloud_percent:
                logger.info(f"{status_prefix} → ОТБРАКОВАНО: облачность над полем={cloud_pct:.1f}%")
                continue

            logger.info(
                f"{status_prefix} → ПРОШЁЛ ✓ | cloud_field={cloud_pct:.1f}% | nodata={nodata_pct:.1%}"
            )

            # Собираем ассеты
            result_assets = {}
            for key in ["visual", "red", "green", "blue", "nir", "scl", "B04", "B03", "B02", "B08"]:
                asset = assets.get(key)
                if asset:
                    result_assets[key] = asset.href
            if "red" not in result_assets and "B04" in result_assets:
                result_assets["red"] = result_assets["B04"]
            if "green" not in result_assets and "B03" in result_assets:
                result_assets["green"] = result_assets["B03"]
            if "blue" not in result_assets and "B02" in result_assets:
                result_assets["blue"] = result_assets["B02"]
            if "nir" not in result_assets and "B08" in result_assets:
                result_assets["nir"] = result_assets["B08"]
            if "visual" not in result_assets and "TCI" in assets:
                result_assets["visual"] = assets["TCI"].href
            if "visual" not in result_assets:
                result_assets["visual"] = visual_href

            passed.append({
                "item_id": item_id,
                "datetime": date_str,
                "cloud_cover_scene": scene_cloud,
                "cloud_cover_field": round(cloud_pct, 1),
                "nodata_percent": round(nodata_pct * 100, 1),
                "assets": result_assets,
            })

        except Exception as e:
            logger.warning(f"{status_prefix} → ОШИБКА при проверке: {type(e).__name__}: {e}")
            continue

    logger.info("=" * 60)
    logger.info(f"Фильтрация завершена. Проверено: {total}, прошло: {len(passed)}")
    logger.info("=" * 60)

    return passed


def run(
    kml_path: str,
    date_range: str = "2022-01-01/2025-12-31",
    max_cloud_percent: float = 10.0,
    max_scene_cloud_prefilter: float = 90.0,
    max_check_items: Optional[int] = None,
) -> List[Dict]:
    """Алиас для обратной совместимости с примером из ТЗ."""
    return filter_pipeline(
        kml_path=kml_path,
        date_range=date_range,
        max_cloud_percent=max_cloud_percent,
        max_scene_cloud_prefilter=max_scene_cloud_prefilter,
        max_check_items=max_check_items,
    )