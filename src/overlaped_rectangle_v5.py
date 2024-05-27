import geopandas as gpd
from fastkml import kml
from shapely.geometry import Point, Polygon
from pyproj import Proj, Transformer
import numpy as np
from geopy.distance import distance
import matplotlib.pyplot as plt
from sentinelhub import SHConfig, BBox, CRS, DataCollection, MimeType, CustomUrlParam, \
    SentinelHubRequest, SentinelHubDownloadClient
import numpy as np
import matplotlib.pyplot as plt
import rasterio
from rasterio.plot import show
import math
import datetime
from aenum import MultiValueEnum
from matplotlib.colors import BoundaryNorm, ListedColormap
from eolearn.core import EOWorkflow, FeatureType, LoadTask, OutputTask, SaveTask, OverwritePermission, linearly_connect_tasks
from eolearn.io import SentinelHubDemTask, SentinelHubEvalscriptTask, SentinelHubInputTask
from shapely.geometry import Point, box

def generate_coordinates(rectangle, step_distance_m):
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
        all_coords.append(edge_points)

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
    
def plot_the_figure(coordinates, points_coords):
    polygon = Polygon(coordinates)

    # Calculate the geometric center
    geometric_center = polygon.centroid

    # Plotting
    x, y = polygon.exterior.xy  # Extracting X and Y coordinates for plotting

    fig, ax = plt.subplots()
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
    #plt.show()


# File path to the KML file
kml_file_path = 'docx\кур-гор-0003.kml'

# Read the KML file and obtain the field coordinates
field_coordinates = read_kml_file(kml_file_path)

# Calculate the bounding box of the field coordinates
rectangle_coords = get_bounding_box(field_coordinates)

points_array = generate_coordinates(rectangle_coords, 100)

# Project the coordinates to a UTM zone
# NOTE: You'll need to determine the appropriate UTM zone for your region
proj_utm = Proj(proj='utm', zone=36, ellps='WGS84', datum='WGS84')
transformer = Transformer.from_proj(Proj('epsg:4326'), proj_utm, always_xy=True)  # from WGS84 to UTM

# Project field coordinates
field_coordinates_utm = [transformer.transform(lat, lon) for lat, lon in field_coordinates]
points_array_utm = [transformer.transform(lat, lon) for lat, lon in points_array]
rectangle_coords_utm = [transformer.transform(lat,lon) for lat,lon in rectangle_coords]

field_polygon = Polygon(field_coordinates_utm)

# Populate the grid with 0s and 1s
grid = populate_grid(points_array_utm, field_polygon) 

plot_the_figure(field_coordinates_utm, grid)

# Set up Sentinel Hub credentials
config = SHConfig()
#config.instance_id = 'your_instance_id'
config.sh_client_id = 'e9258188-d231-4ba5-91d4-5f68f9e3e186'
config.sh_client_secret = 'ad455UJP2OTuEkrK8uVN5L7AN9xzn8KP'

# Define the time range for the NDVI calculation
time_interval = ('2023-07-01', '2023-07-10')

bbox = BBox([rectangle_coords[0][0],rectangle_coords[0][1],rectangle_coords[3][0],rectangle_coords[3][1]], crs=CRS.WGS84)

# maximal cloud coverage (based on Sentinel-2 provided tile metadata)
maxcc = 0.3

# resolution of the request (in metres)
resolution = 100

# time difference parameter (minimum allowed time difference; if two observations are closer than this,
# they will be mosaicked into one observation)
time_difference = datetime.timedelta(hours=2)


input_task = SentinelHubInputTask(
    data_collection=DataCollection.SENTINEL2_L1C,
    bands=["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B10", "B11", "B12"],
    bands_feature=(FeatureType.DATA, "L1C_data"),
    additional_data=[(FeatureType.MASK, "dataMask")],
    resolution=resolution,
    maxcc=maxcc,
    time_difference=time_difference,
    config=config,
    max_threads=3,
)

indices_evalscript = """
    //VERSION=3

    function setup() {
        return {
            input: ["B03","B04","B08","dataMask"],
            output:[{
                id: "indices",
                bands: 2,
                sampleType: SampleType.FLOAT32
            }]
        }
    }

    function evaluatePixel(sample) {
        let ndvi = index(sample.B08, sample.B04);
        let ndwi = index(sample.B03, sample.B08);
        return {
           indices: [ndvi, ndwi]
        };
    }
"""

# this will add two indices: ndvi and ndwi
add_indices = SentinelHubEvalscriptTask(
    features=[(FeatureType.DATA, "indices")],
    evalscript=indices_evalscript,
    data_collection=DataCollection.SENTINEL2_L1C,
    resolution=resolution,
    maxcc=maxcc,
    time_difference=time_difference,
    config=config,
    max_threads=3,
)

add_dem = SentinelHubDemTask(
    feature="dem", data_collection=DataCollection.DEM_COPERNICUS_30, resolution=resolution, config=config
)

add_l2a_and_scl = SentinelHubInputTask(
    data_collection=DataCollection.SENTINEL2_L2A,
    bands=["B01", "B02", "B03", "B04", "B05", "B06", "B07", "B08", "B8A", "B09", "B11", "B12"],
    bands_feature=(FeatureType.DATA, "L2A_data"),
    additional_data=[(FeatureType.MASK, "SCL")],
    resolution=resolution,
    maxcc=maxcc,
    time_difference=time_difference,
    config=config,
    max_threads=3,
)

save = SaveTask(path="overlaped_rect_v4", overwrite_permission=OverwritePermission.OVERWRITE_FEATURES)

output_task = OutputTask("eopatch")

workflow_nodes = linearly_connect_tasks(input_task, add_indices, add_l2a_and_scl, add_dem, save, output_task)
workflow = EOWorkflow(workflow_nodes)

result = workflow.execute(
    {
        workflow_nodes[0]: {"bbox": bbox, "time_interval": time_interval},
        workflow_nodes[-2]: {"eopatch_folder": "eopatch"},
    }
)

eopatch = result.outputs["eopatch"]
#eopatch

#eopatch.plot((FeatureType.DATA, "L1C_data"), times=[0], rgb=[3, 2, 1])
#plt.axis(False);


class SCL(MultiValueEnum):
    """Enum class containing basic LULC types"""

    NO_DATA = "no data", 0, "#000000"
    SATURATED_DEFECTIVE = "saturated / defective", 1, "#ff0004"
    DARK_AREA_PIXELS = "dark area pixels", 2, "#868686"
    CLOUD_SHADOWS = "cloud shadows", 3, "#774c0b"
    VEGETATION = "vegetation", 4, "#10d32d"
    BARE_SOILS = "bare soils", 5, "#ffff53"
    WATER = "water", 6, "#0000ff"
    CLOUDS_LOW_PROBA = "clouds low proba.", 7, "#818181"
    CLOUDS_MEDIUM_PROBA = "clouds medium proba.", 8, "#c0c0c0"
    CLOUDS_HIGH_PROBA = "clouds high proba.", 9, "#f2f2f2"
    CIRRUS = "cirrus", 10, "#bbc5ec"
    SNOW_ICE = "snow / ice", 11, "#53fffa"

    @property
    def rgb(self):
        return [c / 255.0 for c in self.rgb_int]

    @property
    def rgb_int(self):
        hex_val = self.values[2][1:]
        return [int(hex_val[i : i + 2], 16) for i in (0, 2, 4)]


scl_bounds = [-0.5 + i for i in range(len(SCL) + 1)]
scl_cmap = ListedColormap([x.rgb for x in SCL], name="scl_cmap")
scl_norm = BoundaryNorm(scl_bounds, scl_cmap.N)

fig, ax = plt.subplots(1, 1, figsize=(10, 10))

im = plt.imshow(eopatch.mask["SCL"][0].squeeze(), cmap=scl_cmap, norm=scl_norm)
#plt.axis(False)


cb = fig.colorbar(im, orientation="horizontal", pad=0.01, aspect=100)
cb.ax.tick_params(labelsize=20)
cb.set_ticks([entry.values[1] for entry in SCL])
cb.ax.set_xticklabels([entry.values[0] for entry in SCL], rotation=45, fontsize=15, ha="right");
plt.show()
