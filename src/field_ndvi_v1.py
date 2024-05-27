import json
from datetime import datetime, timedelta
from sentinelhub import SentinelHubRequest, SHConfig, DataCollection, MimeType, BBox, bbox_to_dimensions, CRS
from lxml import etree
import numpy as np
import xml.etree.ElementTree as ET
import simplekml
import math

# Your Sentinel Hub credentials
config = SHConfig()
#config.instance_id = 'your-instance-id'
config.sh_client_id = 'e9258188-d231-4ba5-91d4-5f68f9e3e186'
config.sh_client_secret = 'ad455UJP2OTuEkrK8uVN5L7AN9xzn8KP'
config.save()

# NDVI calculation function
def calculate_ndvi(b8, b4):
    # The formula is (NIR - RED) / (NIR + RED)
    with np.errstate(divide='ignore', invalid='ignore'):
        return (b8 - b4) / (b8 + b4)

# Parse a KML file for coordinates
def parse_kml(kml_file):
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

# Function to create requests for NDVI values from Sentinel-2
def create_request(field_point, date):
    evalscript = """
        //VERSION=3
        function setup() {
            return {
                input: ["B04", "B08"],
                output: { bands: 1 }
            };
        }
        function evaluatePixel(sample) {
            var ndvi = (sample.B08 - sample.B04) / (sample.B08 + sample.B04);
            return [ndvi];
        }
    """
    resolution = 10  # 10m resolution
    size = bbox_to_dimensions(bbox, resolution)
    return SentinelHubRequest(
        data_folder='path_to_store_images',
        evalscript=evalscript,
        input_data=[SentinelHubRequest.input_data(
            data_collection=DataCollection.SENTINEL2_L1C,
            time_interval=(date, date + timedelta(days=1))
        )],
        responses=[
            SentinelHubRequest.output_response('default', MimeType.TIFF)
        ],
        bbox=bbox,
        size=size,
        config=config
    )

# Load field coordinates from KML
field_points = parse_kml('docx\кур-гор-0003.kml')

# Create a range of dates
date_ranges = [datetime(2021, month, 1) for month in range(4, 9)]


# Gather NDVI data
ndvi_data = []

for point in field_points:
    # Convert coordinates to BBox object, here you might need to adjust the buffer size
    # to capture the specific area you're interested in.
    bbox = BBox(bbox=[point[1], point[0], point[1] + 0.01, point[0] + 0.01], crs=CRS.WGS84)
    break
    for start_date in date_ranges:
        temp_data = []
        for _ in range(5): # We want at least 5 values for each month
            request = create_request(bbox, start_date)
            ndvi_response = request.get_data(save_data=True)
            ndvi = calculate_ndvi(ndvi_response[-1][..., 1], ndvi_response[-1][..., 0])
            temp_data.append(ndvi.tolist())
            start_date += timedelta(days=6) # Assuming we skip 6 days to get a new image
        ndvi_data.append({
            'date': start_date.strftime('%Y-%m-%d'),
            'coordinates': point,
            'ndvi_values': temp_data
        })

# Save as JSON
with open('docx\кур-гор-0003.json', 'w') as json_file:
    json.dump(ndvi_data, json_file, indent=4)

print("NDVI data has been saved to 'field_ndvi_data.json'")