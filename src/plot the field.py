from pykml import parser
from shapely.geometry import Polygon, Point
import matplotlib.pyplot as plt

# Load the KML file
with open('docx\кур-гор-0003.kml', 'r') as kml_file:
    kml_content = parser.parse(kml_file).getroot()

# Extract the coordinates of the field outline from the KML
# This assumes that your KML field outline is in a 'Polygon' element
coordinates = []
for coordinate in kml_content.Document.Placemark.Polygon.outerBoundaryIs.LinearRing.coordinates.text.strip().split():
    lon, lat = map(float, coordinate.split(','))
    coordinates.append((lon, lat))  # Appending as (Longitude, Latitude)

# Create a Shapely Polygon from the coordinates
polygon = Polygon(coordinates)

# Calculate the geometric center
geometric_center = polygon.centroid

# Print the geometric center coordinates
print(f"Geometric Center (Latitude, Longitude): ({geometric_center.y}, {geometric_center.x})")

# Plotting
x, y = polygon.exterior.xy  # Extracting X and Y coordinates for plotting

fig, ax = plt.subplots()
ax.plot(x, y, label='Field Outline')  # Plot the outline of the field
ax.plot(geometric_center.x, geometric_center.y, 'o', color='red', label='Geometric Center')  # Plot the geometric center
ax.set_xlabel('Longitude')
ax.set_ylabel('Latitude')
ax.set_title('Field and its Geometric Center')
ax.legend()

# Display the plot
plt.show()