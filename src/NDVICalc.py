import os
from pathlib import Path
import json
import fsspec
from fastkml import kml
import mgrs
import rasterio
from rasterio.mask import mask
from shapely.geometry import Polygon, mapping
import numpy as np

def read_kml_polygon_coords(kml_path):
    """
    Читает KML-файл и возвращает координаты первого полигона.
    """
    with open(kml_path, 'rb') as f:
        k = kml.KML()
        k.from_string(f.read())

    for feature in k.features():
        for placemark in feature.features():
            geom = placemark.geometry
            if geom and geom.geom_type == 'Polygon':
                # Берём внешнее кольцо полигона
                coords = list(geom.exterior.coords)
                return coords
    return None

def calculate_centroid(coords):
    """
    Вычисляет центральную точку полигона (простое среднее).
    """
    lngs, lats = zip(*coords)
    centroid_lat = sum(lats) / len(lats)
    centroid_lon = sum(lngs) / len(lngs)
    return centroid_lon, centroid_lat

def get_mgrs_tile(lon, lat):
    """
    Возвращает MGRS-тайл (например, '37UDS') для координат.
    """
    m = mgrs.MGRS()
    mgrs_tile = m.toMGRS(lat, lon, MGRSPrecision=0)  # MGRSPrecision=0 -> 100km tile
    return mgrs_tile

def parse_mgrs_tile(mgrs_tile):
    """
    Разбирает MGRS-тайл на зону и квадрат (например, '37UDS' -> zone='37', square='UDS').
    """
    zone = mgrs_tile[:2]
    square = mgrs_tile[2:]
    return zone, square

def get_sentinel_json_paths(mgrs_zone, mgrs_square, years=[2022], month=5):
    """
    Генерирует список путей к JSON-файлам в S3 для заданного MGRS-квадрата и дат.
    """
    base_path = f"sentinel-s2-l2a-cogs/{mgrs_zone}"
    json_paths = []

    for year in years:
        for day in range(1, 32):  # 1-31
            date_str = f"{year}{month:02d}{day:02d}"
            folder_name = f"S2A_{mgrs_zone}{mgrs_square}_{date_str}_0_L2A"
            # Месяц в пути S3 **без ведущего нуля**
            s3_path = f"{base_path}/{mgrs_square[0]}/{mgrs_square[1:]}/{year}/{month}/{folder_name}/{folder_name}.json"
            json_paths.append((s3_path, date_str, folder_name))

    return json_paths

def download_json_via_fsspec(path, date_str, folder_name, output_dir, s3_fs, mgrs_zone, mgrs_square, original_kml_path):
    """
    Скачивает JSON-файл через fsspec и сохраняет его в нужную папку.
    Если файл уже существует, не скачивает повторно.
    """
    s3_path = f"s3://sentinel-cogs/{path}"

    # Извлекаем год, месяц, день из date_str
    year = date_str[:4]
    month_num = int(date_str[4:6])  # Месяц без ведущего нуля
    day = date_str[6:8]
    date_folder = f"{year}-{month_num}-{day}"

    # Полный MGRS-квадрат: zone + square
    full_mgrs = f"{mgrs_zone}{mgrs_square}"

    # Создаём путь: ../out/{full_mgrs}/{year-month-day}/
    save_dir = Path("../out") / full_mgrs / date_folder
    save_dir.mkdir(parents=True, exist_ok=True)

    print(f"[DEBUG] Папка для сохранения файлов: {save_dir}")

    file_path = save_dir / f"{folder_name}.json"

    # Проверяем, существует ли файл
    if file_path.exists():
        print(f"[DEBUG] JSON-файл уже существует: {file_path}")
        # Читаем существующий файл
        with open(file_path, 'rb') as f:
            content = f.read()
    else:
        try:
            with s3_fs.open(s3_path, 'rb') as f:
                content = f.read()

            with open(file_path, 'wb') as out_f:
                out_f.write(content)

            print(f"[DEBUG] JSON-файл скачан: {file_path}")

        except FileNotFoundError:
            # Не выводим сообщение о "файле не найден"
            return
        except Exception as e:
            print(f"Ошибка при обработке {s3_path}: {e}")
            return

    # Читаем JSON и извлекаем eo:cloud_cover
    data = json.loads(content)
    cloud_cover = data.get('properties', {}).get('eo:cloud_cover')

    if cloud_cover is not None and cloud_cover < 10:
        print(f"{s3_path} -> eo:cloud_cover = {cloud_cover}% -> NDVI needed")
        # Вызываем функцию для расчёта NDVI
        calculate_ndvi_from_tif(s3_fs, folder_name, path, save_dir, date_folder, full_mgrs, original_kml_path)
    else:
        print(f"{s3_path} -> eo:cloud_cover = {cloud_cover}% -> skipped")

def calculate_ndvi_from_tif(s3_fs, folder_name, json_path, save_dir, date_folder, full_mgrs, original_kml_path):
    """
    Скачивает GeoTIFF-файл NDVI (B08 / B04) и считает интегральный NDVI в границах поля.
    Файлы сохраняются в ../out/{full_mgrs}/{date_folder}/
    """
    print(f"[DEBUG] Папка для сохранения TIFF файлов: {save_dir}")

    # save_dir уже папка ../out/{full_mgrs}/{date_folder}/

    # Определяем пути к файлам
    b08_file = save_dir / "B08.tif"
    b04_file = save_dir / "B04.tif"

    # Проверяем, есть ли файлы локально
    if b08_file.exists() and b04_file.exists():
        print(f"[DEBUG] Файлы B08 и B04 уже существуют: {b08_file}, {b04_file}")
    else:
        # Путь к B08 и B04 (NIR и RED) — файлы называются просто B08.tif, B04.tif
        base_dir = json_path.rsplit('/', 1)[0]  # Папка с JSON
        b08_path = f"{base_dir}/B08.tif"
        b04_path = f"{base_dir}/B04.tif"

        s3_b08 = f"s3://sentinel-cogs/{b08_path}"
        s3_b04 = f"s3://sentinel-cogs/{b04_path}"

        print(f"[DEBUG] Пытаюсь скачать B08: {s3_b08}")
        print(f"[DEBUG] Пытаюсь скачать B04: {s3_b04}")

        try:
            # Скачиваем B08 и B04 в память
            with s3_fs.open(s3_b08, 'rb') as f:
                b08_bytes = f.read()
            with s3_fs.open(s3_b04, 'rb') as f:
                b04_bytes = f.read()

            print(f"[DEBUG] Успешно скачаны B08 и B04 для {folder_name}")

            # Сохраняем файлы в нужную папку
            with open(b08_file, 'wb') as f:
                f.write(b08_bytes)
            with open(b04_file, 'wb') as f:
                f.write(b04_bytes)

            print(f"[DEBUG] Временные файлы сохранены: {b08_file}, {b04_file}")

        except FileNotFoundError:
            print(f"[DEBUG] Один из файлов B08/B04 не найден для {folder_name}")
            return
        except Exception as e:
            print(f"Ошибка при скачивании B08/B04 для {folder_name}: {e}")
            return

    # Загружаем координаты поля из оригинального KML-файла
    kml_path = original_kml_path
    coords = read_kml_polygon_coords(kml_path)
    if not coords:
        print("Полигон не найден для NDVI.")
        return

    # Создаём геометрию поля
    poly = Polygon(coords)

    # Открываем изображения и вычисляем NDVI
    try:
        with rasterio.open(b08_file) as src_b08:
            # Преобразуем координаты полигона в проекцию изображения
            geom = mapping(poly)
            out_image, out_transform = mask(src_b08, shapes=[geom], crop=True, nodata=0)
            b08 = out_image[0].astype(float)

        with rasterio.open(b04_file) as src_b04:
            out_image, out_transform = mask(src_b04, shapes=[geom], crop=True, nodata=0)
            b04 = out_image[0].astype(float)

        # Вычисляем NDVI
        ndvi = (b08 - b04) / (b08 + b04 + 1e-10)  # Добавляем малую величину, чтобы избежать деления на 0
        ndvi = np.ma.masked_where(np.isnan(ndvi), ndvi)  # Маскируем NaN

        # Считаем интегральный NDVI (среднее по маске)
        if np.ma.is_masked(ndvi):
            mean_ndvi = ndvi.mean()
        else:
            mean_ndvi = np.mean(ndvi)

        print(f"Интегральный NDVI для {folder_name}: {mean_ndvi:.4f}")

    except ValueError as e:
        if "Input shapes do not overlap raster" in str(e):
            print(f"Ошибка: Полигон не пересекается с изображением для {folder_name}.")
        else:
            print(f"Ошибка при расчёте NDVI для {folder_name}: {e}")
    except Exception as e:
        print(f"Ошибка при расчёте NDVI для {folder_name}: {e}")

def main(kml_path):
    coords = read_kml_polygon_coords(kml_path)
    if not coords:
        print("Полигон не найден в KML-файле.")
        return

    lon, lat = calculate_centroid(coords)
    print(f"Центр полигона: {lon}, {lat}")

    mgrs_tile = get_mgrs_tile(lon, lat)
    print(f"MGRS-тайл: {mgrs_tile}")

    zone, square = parse_mgrs_tile(mgrs_tile)
    print(f"Зона: {zone}, Квадрат: {square}")

    # Определяем имя KML-файла без расширения
    kml_name = Path(kml_path).stem
    print(f"Имя KML-файла: {kml_name}")
    # output_dir больше не используется, т.к. папка формируется внутри download_json_via_fsspec

    json_paths = get_sentinel_json_paths(zone, square, years=[2022], month=5)

    # Инициализируем S3-файловую систему (публичный бакет, без авторизации)
    s3_fs = fsspec.filesystem('s3', anon=True)

    print("\nСкачиваю JSON-файлы через fsspec/s3fs...")
    for path, date_str, folder_name in json_paths:
        download_json_via_fsspec(path, date_str, folder_name, None, s3_fs, zone, square, kml_path)

if __name__ == "__main__":
    # Укажите путь к вашему KML-файлу
    kml_file_path = "кур-гор-0117.kml"
    if not os.path.exists(kml_file_path):
        print(f"Файл {kml_file_path} не найден.")
    else:
        main(kml_file_path)