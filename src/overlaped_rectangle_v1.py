from fastkml import kml
from shapely.geometry import Point, Polygon
from pyproj import Proj, Transformer
import numpy as np

def read_kml_file(filename):
    """Reads a KML file and returns the coordinates of the Placemark."""
    with open(filename, 'rb') as file:
        doc = file.read()
        k = kml.KML()
        k.from_string(doc)
        placemark = list(list(k.features())[0].features())[0]
        return list(placemark.geometry.exterior.coords)

def get_bounding_box(coordinates):
    """Gets the bounding box of the field."""
    lats, lons = zip(*coordinates)
    return min(lats), max(lats), min(lons), max(lons)

def create_grid(x1, y1, x2, y2, cell_size):
    """Creates a grid over the bounding rectangle."""
    lat_points = int(np.ceil((x2-x1) / cell_size))
    lon_points = int(np.ceil((y2-y1) / cell_size))

    grid = np.zeros((lat_points, lon_points), dtype=np.int8)
    return grid, x1, y1

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

# File path to the KML file
kml_file_path = 'docx\кур-гор-0003.kml'

# Read the KML file and obtain the field coordinates
field_coordinates = read_kml_file(kml_file_path)

# Calculate the bounding box of the field coordinates
x1, x2, y1, y2 = get_bounding_box(field_coordinates)

# Project the coordinates to a UTM zone
# NOTE: You'll need to determine the appropriate UTM zone for your region
proj_utm = Proj(proj='utm', zone=33, ellps='WGS84', datum='WGS84')
transformer = Transformer.from_proj(Proj('epsg:4326'), proj_utm, always_xy=True)  # from WGS84 to UTM

# Project field coordinates
field_coordinates_utm = [transformer.transform(lat, lon) for lat, lon in field_coordinates]
field_polygon = Polygon(field_coordinates_utm)

# Create a grid over the bounding box with 100x100 meter cells
cell_size = 100  # In meters
grid, lat_min, lon_min = create_grid(x1, y1, x2, y2, cell_size)

# Populate the grid with 0s and 1s
grid = populate_grid(grid, field_polygon, transformer, lat_min, lon_min, 1e-3)  # Convert cell_size from meters to degrees

# Resulting grid
print(grid)

# NOTE: In the above code, the 'populate_grid' function uses 1e-3 for cell size conversion
# from meters to degrees. This is just an approximation, as the conversion varies depending
# on the latitude. You can either project the entire grid or adjust the conversion
# factor accordingly.