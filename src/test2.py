import cv2
import numpy as np
from skimage import feature
import skimage.measure

# Loading the image
image = cv2.imread('Figure_1.png', 0)

# Edge detection
edges = feature.canny(image, sigma=0.8)

# Binarize the image
binary = np.where(edges > 0, 1, 0)

# Applying dilation and erosion to remove some noise
kernel = np.ones((5,5),np.uint8)
dilation = cv2.dilate(binary.astype(np.uint8), kernel, iterations = 1 )

# Identifying all the connected components (objects) in the image
labels = skimage.measure.label(dilation)

# Prepare an empty array (this will store whether each pixel is within a rectangle)
rectangles_mask = np.zeros_like(labels, dtype=bool)

image_with_rectangles = np.copy(image)

# Iterate over the detected objects
for label in np.unique(labels):
    # Skip the background object
    if label == 0:
        continue

    # Create a mask for the current object
    object_mask = np.where(labels == label, 1, 0).astype(np.uint8)

    # Find contours in the object
    contours, _ = cv2.findContours(object_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    # find the inscribed rectangle for each contour
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)

        # Draw the rectangle on the original image
        cv2.rectangle(image_with_rectangles, (x, y), (x + width, y + height), (255,255,255), 2)

        # Update the rectangles mask
        rectangles_mask[y:y+height, x:x+width] = True

# Save the image to a file
cv2.imwrite('res2.png', image_with_rectangles)