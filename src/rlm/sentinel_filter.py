"""
Двухэтапная фильтрация снимков Sentinel-2 L2A.

Этап 1 — Грубая фильтрация через STAC API (intersects + cloud pre-filter).
Этап 2 — Точная пиксельная проверка: покрытие поля + nodata + облачность по SCL.

Использует COG (Cloud Optimized GeoTIFF) — rasterio читает только нужные регионы
удалённых файлов через HTTP Range Requests, без скачивания целых файлов.
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.mask import mask
from rasterio.transform import rowcol
from shapely.geometry import Polygon, MultiPolygon, mapping, shape
from pystac_client import Client

logger = logging.getLogger(__name__)

# Классы SCL, относящиеся к облакам
CLOUD_SCL_CLASSES = {8, 9, 10, 3}  # 8=Cloud medium, 9=Cloud high, 10=Thin cirrus, 3=Cloud shadows

# STAC API endpoint
STAC_API_URL = "https://earth-search.aws.element84.com/v1"


def _load_field_polygon(kml_path: str) -> Polygon:
    """Загружает полигон поля из KML, возвращает в EPSG:4326."""
    gdf = gpd.read_file(kml_path)
    if gdf.empty:
        raise ValueError(f"KML {kml_path} не содержит геометрии")
    if gdf.crs is None:
        gdf = gdf.set_crs("EPSG:4326")
    else:
        gdf = gdf.to_crs("EPSG:4326")

    geom = gdf.geometry.iloc[0]
    if geom.geom_type == "MultiPolygon":
        # Берём самый большой полигон
        geom = max(geom.geoms, key=lambda g: g.area)
    return geom


def _polygon_fully_within_bounds(polygon_4326: Polygon, src_bounds, src_crs) -> bool:
    """Проверяет, что полигон ПОЛНОСТЬЮ попадает в bounds снимка."""
    from shapely.geometry import box
    import pyproj

    # Перепроецируем полигон в CRS снимка
    transformer = pyproj.Transformer.from_crs("EPSG:4326", src_crs, always_xy=True)
    coords = [transformer.transform(x, y) for x, y in polygon_4326.exterior.coords]
    polygon_proj = Polygon(coords)

    # Bounds снимка как полигон
    scene_box = box(*src_bounds)

    return scene_box.contains(polygon_proj)


def _check_nodata_inside_polygon(
    src_url: str, polygon_4326: Polygon, src_crs
) -> float:
    """
    Читает пиксели внутри полигона из бэнда (B04) и возвращает долю nodata.
    Использует COG windowed read — только нужный регион.
    """
    import pyproj

    with rasterio.open(src_url) as src:
        # Перепроецируем полигон в CRS снимка
        transformer = pyproj.Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)

        def _transform_polygon(poly):
            coords = [transformer.transform(x, y) for x, y in poly.exterior.coords]
            return Polygon(coords)

        if polygon_4326.geom_type == "MultiPolygon":
            polygon_proj = MultiPolygon([_transform_polygon(p) for p in polygon_4326.geoms])
        else:
            polygon_proj = _transform_polygon(polygon_4326)

        # Читаем только область полигона (COG windowed read)
        try:
            out_image, out_transform = mask(
                src, [mapping(polygon_proj)], crop=True, nodata=0, all_touched=True
            )
        except ValueError:
            # Полигон не пересекается с растром
            return 1.0  # 100% nodata

        data = out_image[0]
        total_pixels = data.size
        if total_pixels == 0:
            return 1.0

        # Sentinel-2 L2A: nodata = 0, valid pixels > 0
        nodata_pixels = np.sum(data == 0)
        nodata_percent = nodata_pixels / total_pixels

        logger.debug(
            f"  nodata check: {nodata_pixels}/{total_pixels} = {nodata_percent:.1%}"
        )
        return nodata_percent


def _check_cloud_over_field(
    scl_url: str, polygon_4326: Polygon
) -> float:
    """
    Читает SCL-слой в области полигона и возвращает процент облачных пикселей.
    Использует COG windowed read.
    """
    import pyproj

    with rasterio.open(scl_url) as src:
        transformer = pyproj.Transformer.from_crs("EPSG:4326", src.crs, always_xy=True)

        def _transform_polygon(poly):
            coords = [transformer.transform(x, y) for x, y in poly.exterior.coords]
            return Polygon(coords)

        if polygon_4326.geom_type == "MultiPolygon":
            polygon_proj = MultiPolygon([_transform_polygon(p) for p in polygon_4326.geoms])
        else:
            polygon_proj = _transform_polygon(polygon_4326)

        try:
            out_image, out_transform = mask(
                src, [mapping(polygon_proj)], crop=True, nodata=0, all_touched=True
            )
        except ValueError:
            return 100.0

        scl = out_image[0]
        total_pixels = np.sum(scl > 0)  # исключаем nodata
        if total_pixels == 0:
            return 100.0

        cloud_pixels = np.sum(np.isin(scl, list(CLOUD_SCL_CLASSES)))
        cloud_percent = cloud_pixels / total_pixels * 100

        logger.debug(
            f"  cloud check: {cloud_pixels}/{total_pixels} = {cloud_percent:.1f}%"
        )
        return cloud_percent


def filter_pipeline(
    kml_path: str,
    date_range: str = "2022-01-01/2025-12-31",
    max_cloud_percent: float = 10.0,
    max_scene_cloud_prefilter: float = 90.0,
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
        Максимально допустимый процент облачности над полем (по SCL). По умолчанию 10%.
    max_scene_cloud_prefilter : float
        Предварительный фильтр по общей облачности сцены. По умолчанию 90%.

    Возвращает
    ----------
    List[Dict] — список прошедших фильтрацию снимков. Каждый элемент:
        item_id, datetime, cloud_cover_scene, cloud_cover_field,
        nodata_percent, assets (dict с href для visual, red, green, blue, nir, scl)
    """
    logger.info("=" * 60)
    logger.info("Запуск filter_pipeline")
    logger.info(f"  KML: {kml_path}")
    logger.info(f"  Период: {date_range}")
    logger.info(f"  Порог облачности над полем: {max_cloud_percent}%")
    logger.info(f"  Предфильтр общей облачности: {max_scene_cloud_prefilter}%")
    logger.info("=" * 60)

    # ── Этап 1: STAC-поиск ──
    logger.info("Этап 1: Поиск сцен через STAC API (intersects)...")

    field_polygon = _load_field_polygon(kml_path)
    logger.info(f"  Полигон поля: {field_polygon.area:.6f} кв.град, центр ~({field_polygon.centroid.x:.4f}, {field_polygon.centroid.y:.4f})")

    client = Client.open(STAC_API_URL)
    search = client.search(
        collections=["sentinel-2-l2a"],
        intersects=mapping(field_polygon),
        datetime=date_range,
        query={"eo:cloud_cover": {"lte": max_scene_cloud_prefilter}},
        max_items=None,  # Все снимки за период
    )

    items = list(search.items())
    logger.info(f"  Найдено снимков (общая облачность ≤ {max_scene_cloud_prefilter}%): {len(items)}")

    if not items:
        logger.warning("Снимки не найдены. Проверьте период и геометрию поля.")
        return []

    # ── Этап 2: Пиксельная проверка ──
    logger.info(f"Этап 2: Пиксельная проверка {len(items)} снимков...")
    logger.info(f"  Критерии: покрытие 100%, nodata=0%, облачность над полем ≤ {max_cloud_percent}%")

    passed = []
    total = len(items)

    for i, item in enumerate(items):
        item_id = item.id
        props = item.properties
        date_str = props.get("datetime", "")
        scene_cloud = float(props.get("eo:cloud_cover", 99.0))

        status_prefix = f"  [{i+1:3d}/{total}] {item_id} | {date_str[:10]} | scene_cloud={scene_cloud:.0f}%"

        # Получаем href нужных ассетов. В pystac item.assets — dict[str, pystac.Asset]
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
            # A. Проверка покрытия
            with rasterio.open(visual_href) as vis_src:
                vis_bounds = vis_src.bounds
                vis_crs = vis_src.crs

            if not _polygon_fully_within_bounds(field_polygon, vis_bounds, vis_crs):
                logger.info(f"{status_prefix} → ОТБРАКОВАНО: поле не полностью в bounds снимка")
                continue

            # Проверка nodata внутри поля (по B04 или другому бэнду)
            nodata_band_url = b04_href if b04_href else visual_href
            nodata_pct = _check_nodata_inside_polygon(
                nodata_band_url, field_polygon, vis_crs
            )
            if nodata_pct > 0:
                logger.info(
                    f"{status_prefix} → ОТБРАКОВАНО: nodata={nodata_pct:.1%} внутри поля"
                )
                continue

            # B. Проверка облачности над полем по SCL
            cloud_pct = _check_cloud_over_field(scl_href, field_polygon)
            if cloud_pct > max_cloud_percent:
                logger.info(
                    f"{status_prefix} → ОТБРАКОВАНО: облачность над полем={cloud_pct:.1f}%"
                )
                continue

            # Всё ОК — снимок проходит
            logger.info(
                f"{status_prefix} → ПРОШЁЛ ✓ | cloud_field={cloud_pct:.1f}% | nodata={nodata_pct:.1%}"
            )

            # Собираем ассеты (pystac Asset → .href)
            result_assets = {}
            for key in ["visual", "red", "green", "blue", "nir", "scl", "B04", "B03", "B02", "B08"]:
                asset = assets.get(key)
                if asset:
                    result_assets[key] = asset.href
            # Fallback: S2 L2A может использовать band names вместо B## нотации
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
            # Fallback: если visual всё ещё нет — используем то, что нашли
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
) -> List[Dict]:
    """Алиас для обратной совместимости с примером из ТЗ."""
    return filter_pipeline(
        kml_path=kml_path,
        date_range=date_range,
        max_cloud_percent=max_cloud_percent,
        max_scene_cloud_prefilter=max_scene_cloud_prefilter,
    )