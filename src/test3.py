import cv2
import numpy as np
import matplotlib.pyplot as plt

# Load a color image in grayscale
img = cv2.imread('image.png', cv2.IMREAD_GRAYSCALE)
cv2.imshow ("grayscale", img)

# Apply edge detection
edges = cv2.Canny(img, 1, 1)

# If you want to visualize the final image where edges are detected
plt.imshow(edges)
plt.show()

ret, edges = cv2.threshold(edges, 1, 255, cv2.THRESH_BINARY)

# Given 'edges' is a 2D Numpy array
contours, hierarchy = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_TC89_KCOS)

# Create a copy of the image to draw contours
contour_img = img.copy()

for cnt in contours:
      rect = cv2.minAreaRect(cnt) # пытаемся вписать прямоугольник
      box = cv2.boxPoints(rect) # поиск четырех вершин прямоугольника
      box = np.intp(box) # округление координат
      cv2.drawContours(img,[box],0,(0,255,0),2) # рисуем прямоугольник

# Saving the image
plt.imshow(img)
plt.show()
