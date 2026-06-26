from pystac_client import Client
import rioxarray
from pykml import parser
import matplotlib.pyplot as plt

# Method returns max 3 items of Sentinel data from "client" provider of region, that includes "bbox"
def FindTheData(bbox):
    api_url = "https://earth-search.aws.element84.com/v1"
    client = Client.open(api_url)    
    collection = "sentinel-2-l2a"
    Res = client.search(
        collections=[collection],
        bbox=bbox,
        query = {
            "eo:cloud_cover": {"lte": 10},
            "s2:nodata_pixel_percentage": {"lte":  10},
        },
        max_items=3,
    )
    if Res.matched()==0:
        return 0
    else:
        return Res

# Method calculates bounding box of the field from "kml_file"
def calculate_bounding_box(kml_file):
    # Parse the KML file
    with open(kml_file) as f:
        doc = parser.parse(f).getroot()

    # Initialize min and max values
    min_lat = float('inf')
    max_lat = float('-inf')
    min_lon = float('inf')
    max_lon = float('-inf')

    # Iterate through all Placemarks in the KML
    for placemark in doc.Document.Placemark:
        # Check for LineString
        if hasattr(placemark, 'LineString') and placemark.LineString is not None:
            coords = placemark.LineString.coordinates.text.strip().split()
            for coord in coords:
                lon, lat, _ = map(float, coord.split(','))  # Ignore altitude
                min_lat = min(min_lat, lat)
                max_lat = max(max_lat, lat)
                min_lon = min(min_lon, lon)
                max_lon = max(max_lon, lon)

        # Check for Polygon
        if hasattr(placemark, 'Polygon') and placemark.Polygon is not None:
            coords = placemark.Polygon.outerBoundaryIs.LinearRing.coordinates.text.strip().split()
            for coord in coords:
                lon, lat = map(float, coord.split(','))  # Ignore altitude
                min_lat = min(min_lat, lat)
                max_lat = max(max_lat, lat)
                min_lon = min(min_lon, lon)
                max_lon = max(max_lon, lon)

    # Return the bounding box as a tuple (min_lon, min_lat, max_lon, max_lat)
    return (min_lon, min_lat, max_lon, max_lat)

def PrintItemData(item):
    assets = item.assets
    print('----------------------')
    print(item.bbox)
    for k, v in item.properties.items():
        print(f"{k}: {v}")
    print(assets["thumbnail"].href)
    
def PlotTheBordersOfField(item, bbox):
    #PrintItemData(item)
    assets = item.assets
    tci_href = assets["visual"].href
    tci = rioxarray.open_rasterio(tci_href)
   # Get the transformation matrix
    transform = tci.rio.transform()

    # Convert geographic coordinates (lon, lat) to pixel indices (row, col)
    #col, row = ~transform * (bbox[0], bbox[1])
    x1 = abs((bbox[0]-item.bbox[0])*tci.shape[1]/(item.bbox[2]-item.bbox[0]))
    y1 = abs((bbox[1]-item.bbox[1])*tci.shape[2]/(item.bbox[3]-item.bbox[1]))
    x2 = abs((bbox[2]-item.bbox[0])*tci.shape[1]/(item.bbox[2]-item.bbox[0]))
    y2 = abs((bbox[3]-item.bbox[1])*tci.shape[2]/(item.bbox[3]-item.bbox[1]))

    # Convert to integer indices
    row1, col1 = int(y1), int(x1)
    row2, col2 = int(y2), int(x2)

    # Check if the indices are within the bounds of the array
    if row1 < 0 or row1 >= tci.shape[1] or col1 < 0 or col1 >= tci.shape[2]:
        raise ValueError("The point is outside the bounds of the GeoTIFF.")
    if row2 < 0 or row2 >= tci.shape[1] or col2 < 0 or col2 >= tci.shape[2]:
        raise ValueError("The point is outside the bounds of the GeoTIFF.")
    tci[0, 2200:2400, 9100:9500].rio.to_raster("out/tci.tif")
    # Plot the cropped image
    #cropped_ds = tci.rio.clip_box(row1,col1,row2,col2)
    #fig, ax = plt.subplots(figsize=(10, 10))
    #cropped_ds.plot(ax=ax)
    #ax.set_title("Cropped GeoTIFF Fragment")
    #plt.show()
    
    print(tci_href)
    

# TODO:
# Calculate the points coords of the field to analize the NDVI
# plot the map fragment with field borders on it
    
kml_file_path = 'input\кур-гор-0003.kml' # Set the path to kml file
bounding_box = calculate_bounding_box(kml_file_path)
print(bounding_box)
data = FindTheData(bounding_box)

if data==0:
    print("No matches found")
else:
    items = data.item_collection()
#    for item in items:
#        PrintItemData(item)
    PlotTheBordersOfField(items[0], bounding_box)
