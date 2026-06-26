import xml.etree.ElementTree as ET
from shapely.geometry import Point, Polygon

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

def populate_grid(grid, field_polygon, transformer, lat_min, lon_min, cell_size):
    """Populates the grid with 1s and 0s depending on whether the cell is inside the field."""
    for i in range(grid.shape[0]):
        for j in range(grid.shape[1]):
            # Convert grid cell to lat/lon
            lat, lon = lat_min + i * cell_size, lon_min + j * cell_size
            # Transform the coordinates to UTM
            x, y = transformer.transform(lat, lon)
            # Determine if the point is within the field polygon
            if field_polygon.contains(Point(x, y)):
                grid[i, j] = 1

    return grid

kml_file_path = 'docx\кур-гор-0003.kml'