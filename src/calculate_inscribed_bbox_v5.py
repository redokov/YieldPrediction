import xml.etree.ElementTree as ET
from shapely.geometry import Polygon, MultiPoint
from scipy.spatial import ConvexHull
from typing import List
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

def write_convex_hull_to_kml(input_coords, output_kml_path):
    hull = ConvexHull(input_coords)
    
    kml = simplekml.Kml()

    pol = kml.newpolygon(name='Convex Hull')
    pol.outerboundaryis.coords = [(input_coords[v, 1], input_coords[v, 0]) for v in hull.vertices]
    pol.style.polystyle.color = simplekml.Color.changealphaint(200, simplekml.Color.green)
    
    kml.save(output_kml_path)

# Change the following line to the path to your KML file
input_kml_file = "docx\кур-гор-0003.kml"
output_kml_file = "docx\кур-гор-0003-bbox.kml"

# Read the original KML file and parse the coordinates
coordinates = parse_kml_coordinates(input_kml_file)

write_convex_hull_to_kml(coordinates, output_kml_file)