from fastkml import kml
from shapely.geometry import Point, Polygon
from pyproj import Proj, Transformer
import numpy as np
from geopy.distance import distance
import simplekml
import math
from scipy.spatial import ConvexHull

def generate_coordinates(rectangle, step_distance_m):
    # Sort rectangle coordinates to consistently determine the corner points
    rectangle.sort(key=lambda x: (x[0], x[1]))

    # Bottom-left and bottom-right points (assuming rectangle is aligned with lat/lon axes)
    bl = rectangle[0]
    br = rectangle[1]
    # Top-left and top-right points
    tl = rectangle[2]
    tr = rectangle[3]

    # Function to interpolate points between two coordinates
    def interpolate(start, end, step_distance_m):
        num_steps = math.ceil(distance(start, end).meters / step_distance_m)
        step_bearing = distance(start, end).m
        coords = [start]
        for i in range(1, num_steps):
            point = distance(meters=step_distance_m*i).destination(start, bearing=step_bearing)
            coords.append((point.latitude, point.longitude))
        return coords

    # Generate points along the bottom and top edge
    points_bottom = interpolate(bl, br, step_distance_m)
    points_top = interpolate(tl, tr, step_distance_m)
    
    # Interpolate points between the corresponding points on the top and bottom edges
    all_coords = []

    for i in range(len(points_bottom)-1):
        edge_points = interpolate(points_bottom[i], points_top[i], step_distance_m)
        all_coords.extend(edge_points)

    return all_coords

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
    return [ (min(lats), min(lons)), (max(lats), min(lons)), (min(lats), max(lons)), (max(lats), max(lons))]

def create_grid(x1, y1, x2, y2, cell_size):
    """Creates a grid over the bounding rectangle."""
    lat_points = int(np.ceil((x2-x1) / cell_size))
    lon_points = int(np.ceil((y2-y1) / cell_size))

    grid = np.zeros((lat_points, lon_points), dtype=np.int8)
    return grid, x1, y1

def populate_grid(grid, field_polygon):
    """Populates the grid with 1s and 0s depending on whether the cell is inside the field."""
    res = []
    for point in grid:
            # Determine if the point is within the field polygon
            if field_polygon.contains(Point (point)):
                res.append((point, True))
            else:
                res.append((point, False))

    return res

def write_convex_hull_to_kml(input_coords, output_kml_path):
    hull = ConvexHull(input_coords)
   
    kml = simplekml.Kml()

    pol = kml.newpolygon(name='Convex Hull')
    pol.outerboundaryis.coords = [input_coords[v] for v in hull.vertices]
    pol.style.polystyle.color = simplekml.Color.changealphaint(200, simplekml.Color.green)
    
    kml.save(output_kml_path)

# File path to the KML file
kml_file_path = 'docx\кур-гор-0003.kml'

# Read the KML file and obtain the field coordinates
field_coordinates = read_kml_file(kml_file_path)

# Calculate the bounding box of the field coordinates
rectangle_coords = get_bounding_box(field_coordinates)
write_convex_hull_to_kml(rectangle_coords, "0003_convex_hull.kml")

points_array = generate_coordinates(rectangle_coords, 100)

# Project the coordinates to a UTM zone
# NOTE: You'll need to determine the appropriate UTM zone for your region
proj_utm = Proj(proj='utm', zone=33, ellps='WGS84', datum='WGS84')
transformer = Transformer.from_proj(Proj('epsg:4326'), proj_utm, always_xy=True)  # from WGS84 to UTM

# Project field coordinates
field_coordinates_utm = [transformer.transform(lat, lon) for lat, lon in field_coordinates]
field_polygon = Polygon(field_coordinates_utm)

# Populate the grid with 0s and 1s
grid = populate_grid(points_array, field_polygon) 


# Resulting grid
#print(grid)