import os
from pathlib import Path
import json
import fsspec
from fastkml import kml
import mgrs

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

def get_sentinel_json_paths(mgrs_zone, mgrs_square, years=[2022, 2023, 2024], month=5):
    """
    Генерирует список путей к JSON-файлам в S3 для заданного MGRS-квадрата и дат.
    """
    base_path = f"sentinel-s2-l2a-cogs/{mgrs_zone}"
    json_paths = []

    for year in years:
        for day in range(1, 32):  # 1-31
            date_str = f"{year}{month:02d}{day:02d}"
            folder_name = f"S2A_{mgrs_zone}{mgrs_square}_{date_str}_0_L2A"
            # Путь: {zone}/{square[0]}/{square[1:]}/{year}/{month_no_zero}/...
            s3_path = f"{base_path}/{mgrs_square[0]}/{mgrs_square[1:]}/{year}/{month}/{folder_name}/{folder_name}.json"
            json_paths.append((s3_path, date_str, folder_name))

    return json_paths

def download_json_via_fsspec(path, date_str, folder_name, output_dir, s3_fs):
    """
    Скачивает JSON-файл через fsspec и сохраняет его в нужную папку.
    """
    s3_path = f"s3://sentinel-cogs/{path}"
    try:
        with s3_fs.open(s3_path, 'rb') as f:
            content = f.read()

        # Извлекаем год, месяц, день из date_str
        year = date_str[:4]
        month_num = int(date_str[4:6])  # Месяц без ведущего нуля
        day = date_str[6:8]
        date_folder = f"{year}-{month_num}-{day}"

        # Создаём путь: ../out/{kml_name}/{year-month-day}/filename.json
        save_dir = output_dir / date_folder
        save_dir.mkdir(parents=True, exist_ok=True)

        file_path = save_dir / f"{folder_name}.json"

        with open(file_path, 'wb') as out_f:
            out_f.write(content)

        # Читаем JSON и извлекаем eo:cloud_cover
        data = json.loads(content)
        cloud_cover = data.get('properties', {}).get('eo:cloud_cover')
        print(f"{s3_path} -> eo:cloud_cover = {cloud_cover}% -> saved to {file_path}")
    except FileNotFoundError:
        print(f"Файл не найден: {s3_path}")
    except Exception as e:
        print(f"Ошибка при обработке {s3_path}: {e}")

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
    output_dir = Path("../out") / kml_name

    json_paths = get_sentinel_json_paths(zone, square, years=[2022, 2023, 2024], month=5)

    # Инициализируем S3-файловую систему (публичный бакет, без авторизации)
    s3_fs = fsspec.filesystem('s3', anon=True)

    print("\nСкачиваю JSON-файлы через fsspec/s3fs...")
    for path, date_str, folder_name in json_paths:
        download_json_via_fsspec(path, date_str, folder_name, output_dir, s3_fs)

if __name__ == "__main__":
    # Укажите путь к вашему KML-файлу
    kml_file_path = "кур-гор-0117.kml"
    if not os.path.exists(kml_file_path):
        print(f"Файл {kml_file_path} не найден.")
    else:
        main(kml_file_path)