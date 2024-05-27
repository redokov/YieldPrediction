import sys
import numpy as np
import cv2 as cv
from skimage import feature


if __name__ == '__main__':
    print(__doc__)

    fn = 'image.png' # путь к файлу с картинкой
    img = cv.imread(fn, 0)

    # Apply edge detection
    edges = feature.canny(img, sigma=1)

    # Convert boolean values to integer and then back to regular Python bool, because skimage's canny returns numpy.bool_
    edges = edges.astype(int)
    ret, thresh = cv.threshold(edges, 1, 255, cv.THRESH_BINARY_INV)
    import matplotlib.pyplot as plt
    plt.imshow(edges, cmap=plt.cm.gray)
    plt.show()
    # ищем контуры и складируем их в переменную contours
    contours, hierarchy = cv.findContours( thresh.copy(), cv.RETR_TREE, cv.CHAIN_APPROX_TC89_KCOS)

    # отображаем контуры поверх изображения
    cv.drawContours( img, contours, -1, (255,0,0), 3, cv.LINE_AA, hierarchy, 1 )
    cv.imshow('contours', img) # выводим итоговое изображение в окно

    cv.waitKey()
    cv.destroyAllWindows()