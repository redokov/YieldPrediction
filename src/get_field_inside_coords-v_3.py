import xml.etree.ElementTree as ET
import shapely.geometry as sg
from shapely.ops import cascaded_union
from shapely.affinity import translate

def parse_kml(kml_file):
    # Parse the KML file and extract coordinates
    tree = ET.parse(kml_file)
    root = tree.getroot()
    coordinates = []
    for placemark in root.findall('.//Placemark'):
        for point in placemark.findall('.//Point'):
            coordinates.append((float(point.find('coordinates').text.split(' ')[0]), float(point.find('coordinates').text.split(' ')[1])))
    return coordinates

def calculate_bounding_box(coordinates):
    # Calculate the bounding box
    if not coordinates:
        return None
    x_min, y_min, x_max, y_max = min(c[0] for c in coordinates), min(c[1] for c in coordinates), max(c[0] for c in coordinates), max(c[1] for c in coordinates)
    return (x_min, y_min, x_max - x_min, y_max - y_min)

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

def main(kml_file, cell_size):
    coordinates = parse_kml(kml_file)
    bounding_box = calculate_bounding_box(coordinates)
    grid = create_grid(bounding_box, cell_size)
    grid = check_grid_cells(grid, coordinates)
    return grid

if __name__ == '__main__':
    kml_file = 'docx\кур-гор-0003.kml'
    cell_size = 100
    grid = main(kml_file, cell_size)
    print(grid)