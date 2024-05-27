import cv2
from skimage import feature
import numpy as np

# Load a color image in grayscale
img = cv2.imread('image.png',0)

# Apply edge detection
edges = feature.canny(img, sigma=0.8)

# Convert boolean values to integer and then back to regular Python bool, because skimage's canny returns numpy.bool_
edges = edges.astype(int)

# Print the two-dimensional array
print(edges)

# If you want to visualize the final image where edges are detected
# Uncomment the following lines
import matplotlib.pyplot as plt
plt.imshow(edges, cmap=plt.cm.gray)
plt.show()

ret, edges = cv2.threshold(edges, 1, 255, cv2.THRESH_BINARY_INV)

# given 'edges' is a 2D Numpy array
contours, hierarchy = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

for cnt in contours:
    # get convex hull and approximate to a polygon
    hull = cv2.convexHull(cnt)
    epsilon = 0.02*cv2.arcLength(hull, True)
    approx = cv2.approxPolyDP(hull, epsilon, True)

    # if the polygon has 4 vertices, we consider it as a rectangle
    if len(approx) == 4:
        x, y, w, h = cv2.boundingRect(approx)
        # draw the rectangle on edges
        cv2.rectangle(edges, (x, y), (x+w, y+h), (255, 255, 255), 2)

# save the edges image to visualize all rectangles
cv2.imwrite('rectangle_edges.png', edges)