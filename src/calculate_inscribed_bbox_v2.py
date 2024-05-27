import xml.etree.ElementTree as ET
import simplekml
import math

def parse_kml_coordinates(kml_file):
    # Parse the KML file
    tree = ET.parse(kml_file)
    root = tree.getroot()
    
    # Namespace map
    nsmap = {'kml': 'http://www.opengis.net/kml/2.2'}
    
    # Find all coordinates in the KML file
    coordinates_list = root.findall('.//kml:coordinates', nsmap)
    
    # Extract the coordinates into a list of tuples (longitude, latitude)
    coords = []
    for coordinates in coordinates_list:
        if coordinates.text:
            coords.extend([tuple(map(float, c.split(',')[:2])) for c in coordinates.text.strip().split()])
    return coords

# Calculate the coordinates of the inscribed rectangle
def distance(p1, p2):
    return math.sqrt((p2[0] - p1[0])**2 + (p2[1] - p1[1])**2)

def inscribe_rectangle(p1, p2, p3, p4):
    side1 = distance(p1, p2)
    side2 = distance(p2, p3)
    width = min(side1, side2)
    length = max(side1, side2)
    return width, length

def calculate_bounding_box(coords):

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
    

    # Return the bounding box as a tuple of coordinates (lower left, upper right)
    return inscribed_rectangle

def create_bbox_kml(bounding_box, output_file):
    kml = simplekml.Kml()
    
    # Define the bounding box as a list of tuples (longitude, latitude)
    bbox_coords = [
        (bounding_box[0][0], bounding_box[0][1]),
        (bounding_box[1][0], bounding_box[0][1]),
        (bounding_box[1][0], bounding_box[1][1]),
        (bounding_box[0][0], bounding_box[1][1]),
        (bounding_box[0][0], bounding_box[0][1]),  # Close the loop
    ]
    
    # Create a new polygon for the bounding box
    pol = kml.newpolygon(name="BoundingBox")
    pol.outerboundaryis.coords = bbox_coords
    
    # Save the bounding box to a new KML file
    kml.save(output_file)

# Change the following line to the path to your KML file
input_kml_file = "docx\кур-гор-0003.kml"
output_kml_file = "docx\кур-гор-0003-bbox.kml"

# Read the original KML file and parse the coordinates
coordinates = parse_kml_coordinates(input_kml_file)

# Calculate the bounding box from the coordinates
bbox = calculate_bounding_box(coordinates)

# Write the bounding box to a new KML file
create_bbox_kml(bbox, output_kml_file)