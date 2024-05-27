# %% [markdown]
# # Example showcasing IO tasks

# %% [markdown]
# Notebook showing a workflow examples for downloading and saving EO imaging data

# %%
%matplotlib inline
import datetime

import matplotlib.pyplot as plt
from aenum import MultiValueEnum
from matplotlib.colors import BoundaryNorm, ListedColormap

from sentinelhub import CRS, BBox, DataCollection, SHConfig

from eolearn.core import EOWorkflow, FeatureType, LoadTask, OutputTask, SaveTask, linearly_connect_tasks
from eolearn.io import SentinelHubDemTask, SentinelHubEvalscriptTask, SentinelHubInputTask
from shapely.geometry import Point, box

# %% [markdown]
# ## Prerequisites
# 
# ### Sentinel Hub account
# 
# In order to use Sentinel Hub services you will need a Sentinel Hub account. If you do not have one yet, you can create a free trial account at [Sentinel Hub webpage](https://www.sentinel-hub.com/trial). If you are a researcher you can even apply for a free non-commercial account at [ESA OSEO page](https://earth.esa.int/aos/OSEO).
# 
# ### Credentials
# 
# Please follow the instructions at [configuration instructions](http://sentinelhub-py.readthedocs.io/en/latest/configure.html) to configure your `sentinelhub` installation. For Processing API request you need to obtain and set your `oauth` client id and secret. 
# 
# <div class="alert alert-info">
# 
# **Note:**
#     
# Instead of providing credentials here we could also configure them beforehand according to [configuration instructions](http://sentinelhub-py.readthedocs.io/en/latest/configure.html).
# </div>

# %%
# In case you put the credentials into the configuration file you can leave this unchanged

CLIENT_ID = "e9258188-d231-4ba5-91d4-5f68f9e3e186"
CLIENT_SECRET = "ad455UJP2OTuEkrK8uVN5L7AN9xzn8KP"

# %%
config = SHConfig()

if CLIENT_ID and CLIENT_SECRET:
    config.sh_client_id = CLIENT_ID
    config.sh_client_secret = CLIENT_SECRET

if config.sh_client_id == "" or config.sh_client_secret == "" or config.instance_id == "":
    print("Warning! To use Sentinel Hub services, please provide the credentials (client ID and client secret).")

# %% [markdown]
# ## Request different types of layers and data collections to an eopatch

# %% [markdown]
# In this workflow example, the input task requests S2 L1C bands at 20m resolution, and other eotasks add `NDVI` features, digital elevation model `DEM`, S2 L2A bands.

# %% [markdown]
# ### General parameters

# %%
# region of interest
# Define the center point of Stavropol city in latitude and longitude
stavropol_center = [41.97, 45.05]  # Long, Lat

# Create the bounding box around the center with a width of 110km (1 degree approx. equals 111km)
offset = 10 / 2 / 111

roi_bbox = BBox(bbox=[stavropol_center[0] - offset, stavropol_center[1] - offset, stavropol_center[0] + offset, stavropol_center[1] + offset], crs=CRS.WGS84) # BBox(bbox=[5.60, 52.68, 5.75, 52.63], crs=CRS.WGS84) 
#roi_bbox = BBox(bbox=[41.9, 44.9, 40.60, 45.08], crs=CRS.WGS84)

# time interval of downloaded data
time_interval = ("2021-04-01", "2021-09-01")

# maximal cloud coverage (based on Sentinel-2 provided tile metadata)
maxcc = 0.8

# resolution of the request (in metres)
resolution = 100

# time difference parameter (minimum allowed time difference; if two observations are closer than this,
# they will be mosaicked into one observation)
time_difference = datetime.timedelta(hours=2)

# %% [markdown]
# ### Tasks

# %% [markdown]
# #### Task for Sentinel-2 L1C data

# %% [markdown]
# The `input_task` will download all 13 Sentinel-2 bands, together with `dataMask`. For all possible bands that can be downloaded from Sentinel-2 data, please see Sentinel Hub [documentation](https://docs.sentinel-hub.com/api/latest/#/data/Sentinel-2-L1C?id=available-bands-and-data).

# %%
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

# %% [markdown]
# #### Task for retrieving NDVI index

# %% [markdown]
# <div class="alert alert-info">
# 
# **Disclaimer:**
#     
# As we already have bands B04 and B08 from the previous task, we could calculate NDVI (or any other index) locally. This task serves as an example how one can use Sentinel Hub service to run the calculation.
# </div>

# %%
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

# %% [markdown]
# <div class="alert alert-info">
# 
# **Note:**
#     
# Requesting float32 data (`SampleType.FLOAT32`) from SH service consumes twice the amount of processing units compared to requesting digital numbers. Please see [processing unit](https://docs.sentinel-hub.com/api/latest/\#/API/processing_unit) documentation for details.
# </div>

# %%
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

# %% [markdown]
# #### Task for Digital Elevation Model Data

# %%
add_dem = SentinelHubDemTask(
    feature="dem", data_collection=DataCollection.DEM_COPERNICUS_30, resolution=resolution, config=config
)

# %% [markdown]
# #### Task for Sentinel-2 L2A and SCL data

# %% [markdown]
# With `SentinelHubInputTask` it is possible to request both L2A and SCL data in one go, optimised for smallest processing unit costs.

# %%
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

# %% [markdown]
# #### Tasks for saving/outputting the eopatch

# %%
save = SaveTask("io_example2")

# %% [markdown]
# In case you'd like to keep the eo-patch in memory after the completion of the workflow

# %%
output_task = OutputTask("eopatch")

# %% [markdown]
# ### Run workflow

# %%
workflow_nodes = linearly_connect_tasks(input_task, add_indices, add_l2a_and_scl, add_dem, save, output_task)
workflow = EOWorkflow(workflow_nodes)

result = workflow.execute(
    {
        workflow_nodes[0]: {"bbox": roi_bbox, "time_interval": time_interval},
        workflow_nodes[-2]: {"eopatch_folder": "eopatch"},
    }
)

# %% [markdown]
# Check contents of eopatch

# %%
eopatch = result.outputs["eopatch"]
eopatch

# %% [markdown]
# ### Plot results

# %% [markdown]
# #### Sentinel-2 L1C RGB bands

# %%
eopatch.plot((FeatureType.DATA, "L1C_data"), times=[3], rgb=[3, 2, 1])
plt.axis(False);

# %% [markdown]
# #### NDVI data

# %%
eopatch.plot((FeatureType.DATA, "indices"), times=[3], channels=[0])
plt.axis(False);

# %% [markdown]
# #### NDWI data

# %%
eopatch.plot((FeatureType.DATA, "indices"), times=[3], channels=[1])
plt.axis(False);

# %% [markdown]
# #### Sentinel-2 L2A RGB bands

# %%
eopatch.plot((FeatureType.DATA, "L2A_data"), times=[3], rgb=[3, 2, 1])
plt.axis(False);

# %% [markdown]
# #### Sentinel-2 Scene Classification Layer (from Sen2cor)

# %%
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

# %%
fig, ax = plt.subplots(1, 1, figsize=(10, 10))
im = plt.imshow(eopatch.mask["SCL"][3].squeeze(), cmap=scl_cmap, norm=scl_norm)
plt.axis(False)

cb = fig.colorbar(im, orientation="horizontal", pad=0.01, aspect=100)
cb.ax.tick_params(labelsize=20)
cb.set_ticks([entry.values[1] for entry in SCL])
cb.ax.set_xticklabels([entry.values[0] for entry in SCL], rotation=45, fontsize=15, ha="right");

# %% [markdown]
# #### Mapzen Digital Elevation Model

# %%
eopatch.plot((FeatureType.DATA_TIMELESS, "dem"))
plt.axis(False);

# %% [markdown]
# ## Load the saved eopatch from disk

# %%
load = LoadTask("io_example")
new_eopatch = load.execute(eopatch_folder="eopatch")

# %% [markdown]
# Compare with existing in memory

# %%
new_eopatch == eopatch


