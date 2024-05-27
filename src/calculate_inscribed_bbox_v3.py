import simplekml
import math

# Read the KML file
kml_file = 'docx\кур-гор-0003.kml'  # Replace with your file name
kml = simplekml.Kml()
kml = kml.open(kml_file)

# Extract the coordinates from the KML file
coordinates = []
for pol in kml.gxfeatures():
    for coor in pol.geometry.exterior.coords:
        coordinates.append((coor[0], coor[1]))

# Calculate the coordinates of the inscribed rectangle
def distance(p1, p2):
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

def inscribe_rectangle(p1, p2, p3, p4):
    side1 = distance(p1, p2)
    side2 = distance(p2, p3)
    width = min(side1, side2)
    length = max(side1, side2)
    return width, length

# Find the inscribed rectangle
max_area = 0
inscribed_rectangle = None
for i in range(len(coordinates)):
    for j in range(i+1, len(coordinates)):
        for k in range(j+1, len(coordinates)):
            for l in range(k+1, len(coordinates)):
                width, length = inscribe_rectangle(coordinates[i], coordinates[j], coordinates[k], coordinates[l])
                area = width * length
                if area > max_area:
                    max_area = area
                    inscribed_rectangle = [coordinates[i], coordinates[j], coordinates[k], coordinates[l]]

# Save the coordinates of the inscribed rectangle to the KML file
inscribed_rect = kml.newpolygon(name="Inscribed Rectangle")
inscribed_rect.outerboundaryis = inscribed_rectangle
kml.save("docx\кур-гор-0003-bbox.kml")
