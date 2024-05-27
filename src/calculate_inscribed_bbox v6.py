import xml.etree.ElementTree as ET
from xml.dom.minidom import Document
import shapely.geometry as sg
from shapely.ops import cascaded_union
from shapely.affinity import translate

def parse_kml_file(kml_path):
    # Parse the KML file
    tree = ET.parse(kml_path)
    root = tree.getroot()

    # KML files use the namespace, find the namespace URL
    namespace = ''
    for elem in root.iter():
        if elem.tag.startswith('{'):
            namespace = elem.tag.split('}')[0].strip('{')
            break

    if namespace:
        search_str = f".//{{{namespace}}}Placemark//{{{namespace}}}Polygon//{{{namespace}}}outerBoundaryIs//{{{namespace}}}LinearRing//{{{namespace}}}coordinates"
    else:
        search_str = ".//Placemark//Polygon//outerBoundaryIs//LinearRing//coordinates"
    
    # Find the coordinates element
    coords_elem = root.find(search_str)
    if coords_elem is None:
        raise ValueError("No coordinates element found in the KML file.")

    # Extract and parse coordinates
    raw_coords = coords_elem.text.strip()
    coord_list = []
    for line in raw_coords.split():
        try:
            lon, lat = line.split(",")[:2]  # Taking only first two values
            coord_list.append((float(lon), float(lat)))
        except ValueError as e:
            print(f"Error parsing line: '{line}'. Error: {e}")

    return coord_list  # List of (longitude, latitude) tuples

def calculate_inscribed_bbox(coord_list):
    # Assuming coord_list is a list of (longitude, latitude) tuples
    # Find the bounding coordinates
    min_lon = min(coord_list, key=lambda x: x[0])[0]
    max_lon = max(coord_list, key=lambda x: x[0])[0]
    min_lat = min(coord_list, key=lambda x: x[1])[1]
    max_lat = max(coord_list, key=lambda x: x[1])[1]

    # Find the center of the bounding box
    center_lon = (min_lon + max_lon) / 2
    center_lat = (min_lat + max_lat) / 2

    # Due to the curvature of the Earth and map projections, the "inscribed" box
    # for complex polygons might not always be truly inscribed within the curve.
    # This is a simplified approximation for small regions.
    # The rectangular geo-box coordinates:
    return {
        'min_lon': min_lon,
        'max_lon': max_lon,
        'min_lat': min_lat,
        'max_lat': max_lat
    }

def create_grid(bounding_box, cell_size):
    # Create a grid based on the bounding box and the desired cell size
    x_min, y_min, width, height = bounding_box
    x_cells = int((width + cell_size - 1) / cell_size)
    y_cells = int((height + cell_size - 1) / cell_size)
    grid = [[0 for _ in range(x_cells)] for _ in range(y_cells)]
    return grid

def check_grid_cells(grid, coordinates):
    # Check if each grid cell contains any of the original coordinates
    for y in range(len(grid)):
        for x in range(len(grid[y])):
            cell_bbox = (x * cell_size + x_min, y * cell_size + y_min, (x + 1) * cell_size, (y + 1) * cell_size)
            cell_contains_coordinates = any(sg.Point(c).within(sg.box(*cell_bbox)) for c in coordinates)
            grid[y][x] = int(cell_contains_coordinates)
    return grid

def create_kml_file(bbox, output_kml_filename):
    # Create the KML document
    doc = Document()

    # Create the root 'kml' element
    kml = doc.createElement('kml')
    kml.setAttribute('xmlns', 'http://www.opengis.net/kml/2.2')
    doc.appendChild(kml)

    # Create 'Document' element
    document = doc.createElement('Document')
    kml.appendChild(document)
    
    # Create 'Placemark' element
    placemark = doc.createElement('Placemark')
    document.appendChild(placemark)
    
    # Create 'name' element (optional)
    name = doc.createElement('name')
    name_text = doc.createTextNode('BBOX')
    name.appendChild(name_text)
    placemark.appendChild(name)

    # Create 'Polygon' element
    polygon = doc.createElement('Polygon')
    placemark.appendChild(polygon)

    # Create 'outerBoundaryIs' element
    outer_boundary_is = doc.createElement('outerBoundaryIs')
    polygon.appendChild(outer_boundary_is)
    
    # Create 'LinearRing' element
    linear_ring = doc.createElement('LinearRing')
    outer_boundary_is.appendChild(linear_ring)

    # Create 'coordinates' element
    coordinates = doc.createElement('coordinates')
    coordinates_text = doc.createTextNode(
        f"{bbox[0]},{bbox[1]},0 "  # min_longitude, min_latitude
        f"{bbox[0]},{bbox[3]},0 "  # min_longitude, max_latitude
        f"{bbox[2]},{bbox[3]},0 "  # max_longitude, max_latitude
        f"{bbox[2]},{bbox[1]},0 "  # max_longitude, min_latitude
        f"{bbox[0]},{bbox[1]},0"   # Close the loop
    )
    coordinates.appendChild(coordinates_text)
    linear_ring.appendChild(coordinates)

    # Write the KML Document to a file
    kml_string = doc.toprettyxml(indent="  ")
    with open(output_kml_filename, 'w') as f:
        f.write(kml_string)
    print(f"KML file saved to {output_kml_filename}")
# Example usage:
kml_path = 'docx\кур-гор-0003.kml'
coordinate_list = parse_kml_file(kml_path)
geo_box = calculate_inscribed_bbox(coordinate_list)
cell_size = 100
grid = create_grid(geo_box, cell_size)
grid = check_grid_cells(grid, coordinate_list)
output_kml_file = 'docx\кур-гор-0003-bbox.kml'
create_kml_file(geo_box, output_kml_file)
print(grid)