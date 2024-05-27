from fastkml import kml
from shapely.geometry import Point, Polygon
from pyproj import Proj, Transformer
import numpy as np
from geopy.distance import distance
import math
from scipy.spatial import ConvexHull
import matplotlib.pyplot as plt

def generate_coordinates(rectangle, step_distance_m, ax):
    # Sort rectangle coordinates to consistently determine the corner points
    rectangle.sort(key=lambda x: (x[0], x[1]))

    # Bottom-left and bottom-right points (assuming rectangle is aligned with lat/lon axes)
    bl = rectangle[0]
    br = rectangle[2]
    # Top-left and top-right points
    tl = rectangle[1]
    tr = rectangle[3]

    # Function to interpolate points between two coordinates
    def interpolate(start, end, step_distance_m, bearing = 90):
        num_steps = math.ceil(distance(start, end).meters / step_distance_m)
        coords = [start]
        point = start
        for i in range(1, num_steps):
            point = distance(meters=step_distance_m).destination(point, bearing)
            coords.append((point.latitude, point.longitude))
        return coords

    # Generate points along the bottom and top edge
    points_left = interpolate(bl, tl, step_distance_m)
    points_right = interpolate(br, tr, step_distance_m)
    
    # Interpolate points between the corresponding points on the top and bottom edges
    all_coords = []

    for i in range(len(points_left)-1):
        edge_points = interpolate(points_left[i], points_right[i], step_distance_m, 0)
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
    delta = 0.001
    lats, lons = zip(*coordinates)
    return [ (min(lats)-delta, min(lons)-delta), (max(lats)+delta, min(lons)-delta), (min(lats)-delta, max(lons)+delta), (max(lats)+delta, max(lons)+delta)]

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
    
def plot_the_figure(coordinates, points_coords, ax):
    polygon = Polygon(coordinates)

    # Calculate the geometric center
    geometric_center = polygon.centroid

    # Plotting
    x, y = polygon.exterior.xy  # Extracting X and Y coordinates for plotting

    
    ax.plot(x, y, label='Field Outline')  # Plot the outline of the field
    for points in points_coords:
        if points[1]:
            ax.plot(points[0][0], points[0][1], 'o', color='green')
        else: 
            ax.plot(points[0][0], points[0][1], 'o', color='red')  
    
    #ax.plot(geometric_center.x, geometric_center.y, 'o', color='red', label='Geometric Center')
    ax.set_xlabel('Longitude')
    ax.set_ylabel('Latitude')
    ax.set_title('Field and its cover')
    ax.legend()

    # Display the plot
    plt.show()

# File path to the KML file
kml_file_path = 'docx\кур-гор-0003.kml'
fig, ax = plt.subplots()

# Read the KML file and obtain the field coordinates
field_coordinates = read_kml_file(kml_file_path)

# Calculate the bounding box of the field coordinates
rectangle_coords = get_bounding_box(field_coordinates)

points_array = generate_coordinates(rectangle_coords, 100, ax)

# Project the coordinates to a UTM zone
# NOTE: You'll need to determine the appropriate UTM zone for your region
#proj_utm = Proj(proj='utm', zone=36, ellps='WGS84', datum='WGS84')
#transformer = Transformer.from_proj(Proj('epsg:4326'), proj_utm, always_xy=True)  # from WGS84 to UTM

# Project field coordinates
#field_coordinates_utm = [transformer.transform(lat, lon) for lat, lon in field_coordinates]
#points_array_utm = [transformer.transform(lat, lon) for lat, lon in points_array]

field_polygon = Polygon(field_coordinates)

# Populate the grid with 0s and 1s
grid = populate_grid(points_array, field_polygon) 

plot_the_figure(field_coordinates, grid, ax)