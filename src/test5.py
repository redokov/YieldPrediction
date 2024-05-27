import cv2
import numpy as np
import matplotlib.pyplot as plt
import random as rng

# Load a color image in grayscale
img = cv2.imread('src\input\image.png', cv2.IMREAD_GRAYSCALE)

cv2.imwrite("src\output\grayscale.png", img)
#cv2.waitKey(0)

edges = cv2.Canny(img, 10, 200)

cv2.imwrite("src\output\canny.png", edges)
#cv2.waitKey(0)

contours, hierarchy = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_TC89_L1)

contours_poly = [None]*len(contours)
boundRect = [None]*len(contours)
centers = [None]*len(contours)
radius = [None]*len(contours)

for i, c in enumerate(contours):
    contours_poly[i] = cv2.approxPolyDP(c, 3, True)
    boundRect[i] = cv2.boundingRect(contours_poly[i])
    centers[i], radius[i] = cv2.minEnclosingCircle(contours_poly[i])
    
    
drawing = np.zeros((edges.shape[0], edges.shape[1], 3), dtype=np.uint8)
    
    
for i in range(len(contours)):
    color = (rng.randint(0,256), rng.randint(0,256), rng.randint(0,256))
    #cv2.drawContours(drawing, contours_poly, i, color)
    #cv2.rectangle(drawing, (int(boundRect[i][0]), int(boundRect[i][1])), \
    #    (int(boundRect[i][0]+boundRect[i][2]), int(boundRect[i][1]+boundRect[i][3])), color, 2)
    if int (radius[i])>20:
        cv2.circle(drawing, (int(centers[i][0]), int(centers[i][1])), int(radius[i]), color, 2)

# save the edges image to visualize all rectangles

cv2.imshow('src\output\rectangle_edges.png', drawing)


#cv2.imshow("canny", edges)
cv2.waitKey(0)