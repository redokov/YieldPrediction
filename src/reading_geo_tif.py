import rasterio
import numpy as np

# Open the Sentinel TCI.tif file
filename = 'src\input\\tci.tif'
# Координаты интересующего объекта
latitude = 43.716516
longitude = 43.526143

# Открываем файл TCI.tif
with rasterio.open(filename) as dataset:
    # Преобразуем географические координаты в координаты пикселей
    py, px = dataset.index(longitude, latitude)

    # Вычисляем смещение для получения прямоугольника 200x200 пикселей
    window = rasterio.windows.Window(px - 100, py - 100, 200, 200)

    # Читаем данные из окна
    clip = dataset.read(1, window=window)
    clip = np.array(clip)

    # Выводим изображение (прямоугольник)
    print(clip)
    with rasterio.open('out\\result.tif', 'w', **dataset.meta) as dst:
        dst.write(clip, 1)