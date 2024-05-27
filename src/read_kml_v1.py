import os
import numpy as np
import matplotlib.pyplot as plt
from pykml import parser
from shapely.geometry import Polygon, Point
from mgrs import MGRS
from sentinelsat import SentinelAPI, read_geojson, geojson_to_wkt
import rasterio
from rasterio.plot import show
from rasterio.mask import mask
from rasterio.features import geometry_mask

# Чтение KML файла и извлечение границ поля
def read_kml(file_path):
    with open(file_path) as f:
        doc = parser.parse(f).getroot()
    coords = doc.Document.Placemark.Polygon.outerBoundaryIs.LinearRing.coordinates.text.strip().split()
    coords = [tuple(map(float, coord.split(','))) for coord in coords]
    return Polygon(coords)

# Преобразование координат в MGRS
def polygon_to_mgrs(polygon):
    mgrs_converter = MGRS()
    centroid = polygon.centroid
    return mgrs_converter.toMGRS(centroid.y, centroid.x)

# Загрузка данных Sentinel
def download_sentinel_data(mgrs_tile, download_path):
    api = SentinelAPI('user', 'password', 'https://scihub.copernicus.eu/dhus')
    footprint = geojson_to_wkt(read_geojson(mgrs_tile))
    products = api.query(footprint,
                         date=('20220101', '20220131'),
                         platformname='Sentinel-2',
                         cloudcoverpercentage=(0, 30))
    api.download_all(products, directory_path=download_path)

# Вычисление NDVI и NDWI
def calculate_indices(band4, band8, band3, band11):
    ndvi = (band8 - band4) / (band8 + band4)
    ndwi = (band3 - band11) / (band3 + band11)
    return ndvi, ndwi

# Разбиение поля на гектары и вычисление средних значений индексов
def process_field(field_polygon, tci_path):
    with rasterio.open(tci_path) as src:
        out_image, out_transform = mask(src, [field_polygon], crop=True)
        out_meta = src.meta.copy()
    
    band4 = out_image[3]
    band8 = out_image[7]
    band3 = out_image[2]
    band11 = out_image[10]
    
    ndvi, ndwi = calculate_indices(band4, band8, band3, band11)
    
    fig, ax = plt.subplots()
    show(out_image, ax=ax)
    ax.plot(*field_polygon.exterior.xy, color='red')
    
    for i in range(0, out_image.shape[1], 100):
        for j in range(0, out_image.shape[2], 100):
            hectare = out_image[:, i:i+100, j:j+100]
            avg_ndvi = np.mean(ndvi[i:i+100, j:j+100])
            avg_ndwi = np.mean(ndwi[i:i+100, j:j+100])
            ax.text(j + 50, i + 50, f'NDVI: {avg_ndvi:.2f}', color='white', fontsize=8, ha='center')
    
    plt.show()

# Основной код
field_polygon = read_kml('field.kml')
mgrs_tile = polygon_to_mgrs(field_polygon)
download_sentinel_data(mgrs_tile, '/tmp')
process_field(field_polygon, '/tmp/tci.tif')
