import numpy as np
import datetime
from sentinelhub import SHConfig, MimeType, CRS, BBox, SentinelHubRequest, DataCollection, bbox_to_dimensions, DownloadRequest
from eolearn.core import EOPatch, EOTask, EOWorkflow, FeatureType
from eolearn.io import SentinelHubInputTask
from eolearn.features import NormalizedDifferenceIndexTask

# Configuration
INSTANCE_ID = "e9258188-d231-4ba5-91d4-5f68f9e3e186"
CLIENT_SECRET = "ad455UJP2OTuEkrK8uVN5L7AN9xzn8KP"

config = SHConfig()
if CLIENT_SECRET:
    config.sh_client_secret = CLIENT_SECRET
if INSTANCE_ID:
    config.instance_id = INSTANCE_ID

# Coordinates for the center of Nalchik
nalchik_coords_wgs84 = [43.4981, 43.6181]  # latitude and longitude
side_km = 10  # size of rectangle
side_in_m = side_km * 1000
bbox = BBox(bbox=[(nalchik_coords_wgs84[1] - side_km / 2 / 111, nalchik_coords_wgs84[0] - side_km / 2 / 111),
                  (nalchik_coords_wgs84[1] + side_km / 2 / 111, nalchik_coords_wgs84[0] + side_km / 2 / 111)], crs=CRS.WGS84)

# Define the NDVI calculation task
ndvi_task = NormalizedDifferenceIndexTask((FeatureType.DATA, 'BANDS'), 
                                          (FeatureType.DATA, 'NDVI'), 
                                          [7, 3])

# Define the input task to fetch data from Sentinel-2 L2A
input_task = SentinelHubInputTask(
    data_collection=DataCollection.SENTINEL2_L2A,
    bands_feature=(FeatureType.DATA, 'BANDS'),
    resolution=10,
    bands=['B04', 'B08'],
    additional_data=[(FeatureType.MASK, 'dataMask', 'IS_DATA')],
    time_difference=datetime.timedelta(hours=2),
    maxcc=0.05,
    config=config
)

# Time range for the given period split monthly
start_date = datetime.date(2023, 5, 1)
end_date = datetime.date(2023, 6, 1)
all_dates = [start_date + datetime.timedelta(days=x) for x in range((end_date-start_date).days)]
monthly_dates = [date for date in all_dates if date.day == 1]

# For demonstration, we're using a smaller area and fewer dates
monthly_dates = monthly_dates[:3]  # Limiting to 3 examples

# Create a workflow which includes cloud filtering
workflow = EOWorkflow(dependencies=[
    Dependency(transform=input_task),
    Dependency(transform=ndvi_task, inputs=[input_task]),
])

# Execute the workflow for each month
ndvi_matrices = []

for date in monthly_dates:
    time_interval = (date, date + datetime.timedelta(days=30))  # 30 days interval for each month
    result = workflow.execute({
        input_task: {'bbox': bbox, 'time_interval': time_interval}
    })
    eopatch = result.eopatch()

    # Extract NDVI and reshape it to the desired matrix
    ndvi_data = eopatch.data['NDVI']
    
    # Assuming that the NDVI has dimensions (Time, Height, Width, Bands)
    # And we're interested only in the mean NDVI value for each 100x100m square
    ndvi_mean_over_time = np.mean(ndvi_data, axis=(0, 3))
    # Use a stride trick to downsample the image
    shape = (ndvi_mean_over_time.shape[0] // 10, 10, ndvi_mean_over_time.shape[1] // 10, 10)
    strides = (ndvi_mean_over_time.strides[0]*10, ndvi_mean_over_time.strides[0], ndvi_mean_over_time.strides[1]*10, ndvi_mean_over_time.strides[1])
    ndvi_matrix = np.lib.stride_tricks.as_strided(ndvi_mean_over_time, shape=shape, strides=strides).mean(axis=(1, 3))
    
    ndvi_matrices.append(ndvi_matrix)
    
    # If needed to save the matrices, it can be done with numpy
    # np.save(f'ndvi_matrix_{date}.npy', ndvi_matrix)

# Print the resulting matrices
for i, matrix in enumerate(ndvi_matrices):
    print(f"\nNDVI Matrix for {monthly_dates[i]}:\n", matrix)