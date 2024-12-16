import os
import glob
import json
import math
import pyproj
import xml.etree.ElementTree as ET

'''
Assumptions made:
- The JGW file is in the same directory as the JPEG file.
- The XML file is in the same directory as the JPEG file.
- The JGW file contains the following parameters in the following order: pixel_size_x, rotation_x, rotation_y, pixel_size_y, upper_left_x, upper_left_y.
- The XML file contains the following fields: copyright, km_reference, date_flown, coordinates, lens_focal_length, resolution.
- From srsName="osgb:BNG" in XML, assuming that we are using british national grid coordinate system by default. 
    This script just converts it to latitude, longitude at the end. 

    If we want to georeference using lat,lon to begin with, we either convert to BNG at the start or add separate logic for lat,lon.
    Defined box is lost upon georeferencing. Did not add anything currently to prevent this as it would mean having more than lat, lon coordinates.

Current status: Needs better testing and integration.
                JGW and XML file names and directories need to be provided
                Integration will probably use `pixel_to_geo_with_transform` function for one coordinate/box at a time, not provide a whole directory.
                    Remove/simplify the directory logic as needed.
'''

# Define the coordinate systems
bng = pyproj.CRS("EPSG:27700")  # British National Grid (BNG)
wgs84 = pyproj.CRS("EPSG:4326")  # WGS84 (latitude, longitude)

# Create a transformer to convert between BNG and WGS84
transformer = pyproj.Transformer.from_crs(bng, wgs84, always_xy=True)

def bng_to_latlon(x_bng, y_bng):
    """
    Convert British National Grid (BNG) coordinates to latitude and longitude (WGS84).
    """
    lon, lat = transformer.transform(x_bng, y_bng)
    return lat, lon  # Return in (latitude, longitude)

def parse_jgw(jgw_file):
    """
    Parse the JGW file and extract transformation parameters.

    Returns: pixel_size_x, rotation_x, rotation_y, pixel_size_y, upper_left_x, upper_left_y.

    - upper_left values are the coordinates of the upper-left corner of the image.
    - pixel_size values are the scale factors for the x and y directions.
    - rotation is the angle of rotation of the image. In our case there is no rotation, but this is included for scalability purposes
        rotation: rotation_x == rotation_y. (value of either indicates rotation angle)
        skewed: rotation_x != rotaion_y.
    """
    with open(jgw_file, 'r') as f:
        jgw = [float(line.strip()) for line in f.readlines()]

    pixel_size_x = jgw[0]  # Pixel size in x-direction (width of a single pixel in the coordinate space)
    # E.g. (pixel_size_x == 0.25) means that each pixel in the image represents 0.25 units (meters) in the coordinate space
 
    rotation_x = jgw[1]    # Rotation (x-axis)
    rotation_y = jgw[2]    # Rotation (y-axis)
    pixel_size_y = jgw[3]  # Pixel size in y-direction (negative for north-up)
    upper_left_x = jgw[4]  # Upper-left x-coordinate
    upper_left_y = jgw[5]  # Upper-left y-coordinate

    return pixel_size_x, rotation_x, rotation_y, pixel_size_y, upper_left_x, upper_left_y


def pixel_to_geo(pixel_x, pixel_y, jgw_params):
    """
    Auxiliarry function:
    Converts pixel coordinates to georeferenced coordinates using JGW parameters.
    """
    pixel_size_x, rotation_x, rotation_y, pixel_size_y, upper_left_x, upper_left_y = jgw_params

    # (Regular distance) + (Rotation accounted distance) + (Upper left corner starting point)
    x_geo = (pixel_x * pixel_size_x) + (pixel_y * rotation_x) + upper_left_x
    y_geo = (pixel_y * pixel_size_y) + (pixel_x * rotation_y) + upper_left_y

    return x_geo, y_geo


def pixel_to_geo_with_transform(pixel_x, pixel_y, jgw_params, center=None, height=None, width=None, rotation_angle=0):
    """
    Convert pixel coordinates to georeferenced coordinates, considering optional rotation, scaling, and translation.

    Args:
        pixel_x, pixel_y: Initial pixel coordinates.
        jgw_params: Parameters from the JGW file (scale, rotation, offsets).
        center: Tuple of (center_x, center_y) for the rotation center (optional).
        height: Height of the bounding box in pixels (optional).
        width: Width of the bounding box in pixels (defaults to height if not provided, optional).
        rotation_angle: Rotation angle in degrees (clockwise) about the center (optional).

    Returns:
        x_geo, y_geo: Transformed georeferenced coordinates.
    """
    # If no center or height/width, treat as a single pixel
    if center is None or height is None:
        return pixel_to_geo(pixel_x, pixel_y, jgw_params)

    # Otherwise, treat as a box and apply transformations
    pixel_size_x, rotation_x, rotation_y, pixel_size_y, upper_left_x, upper_left_y = jgw_params
    center_x, center_y = center
    width = width or height  # Assume square box if width is not provided

    # Translate pixel coordinates to be relative to the center
    rel_x = pixel_x - center_x
    rel_y = pixel_y - center_y

    # Apply rotation transformation
    theta = math.radians(rotation_angle)
    rotated_x = rel_x * math.cos(theta) - rel_y * math.sin(theta)
    rotated_y = rel_x * math.sin(theta) + rel_y * math.cos(theta)

    # Reapply translation to place coordinates back in the original reference frame
    translated_x = rotated_x + center_x
    translated_y = rotated_y + center_y

    # Convert pixel coordinates to georeferenced coordinates using JGW
    x_geo = (translated_x * pixel_size_x) + (translated_y * rotation_x) + upper_left_x
    y_geo = (translated_y * pixel_size_y) + (translated_x * rotation_y) + upper_left_y

    # Convert BNG coordinates (x_geo, y_geo) to latitude/longitude
    lat, lon = bng_to_latlon(x_geo, y_geo)

    return x_geo, y_geo



def parse_xml_metadata(xml_file):
    """
    Parse the XML metadata file to extract useful information.

    Returns: A dictionary containing metadata fields.
    """
    if not os.path.exists(xml_file):
        return {}

    try:
        tree = ET.parse(xml_file)
        root = tree.getroot()
        metadata = {}

        # Extract specific fields from your XML structure
        namespace = {'osgb': 'http://www.ordnancesurvey.co.uk/xml/namespaces/osgb', 'gml': 'http://www.opengis.net/gml'}
        
        metadata['copyright'] = root.findtext('osgb:copyright', default='N/A', namespaces=namespace)
        metadata['km_reference'] = root.findtext('osgb:kmReference', default='N/A', namespaces=namespace)
        metadata['date_flown'] = root.findtext('osgb:dateFlown', default='N/A', namespaces=namespace)
        metadata['coordinates'] = root.find('osgb:kmRectangle/osgb:Rectangle/gml:coordinates', namespaces=namespace).text if root.find('osgb:kmRectangle/osgb:Rectangle/gml:coordinates', namespaces=namespace) is not None else 'N/A'
        metadata['lens_focal_length'] = root.find('osgb:lensFocalLength', namespaces=namespace).text if root.find('osgb:lensFocalLength', namespaces=namespace) is not None else 'N/A'
        metadata['resolution'] = root.find('osgb:resolution', namespaces=namespace).text if root.find('osgb:resolution', namespaces=namespace) is not None else 'N/A'

        return metadata

    except ET.ParseError:
        print(f"Error parsing {xml_file}. Returning empty metadata.")
        return {}


def get_test_data():
    """
    Returns test data for regions and file names.
    """
    regions = [
        {'name': 'region_1', 'initial_x': 500, 'initial_y': 500, 'center': (500, 500), 'height': 100, 'rotation': 15},
        {'name': 'region_2', 'initial_x': 1500, 'initial_y': 1500, 'center': (1500, 1500), 'height': 200, 'rotation': 30},
        {'name': 'region_3', 'initial_x': 2500, 'initial_y': 2500, 'center': (2500, 2500), 'height': 300, 'rotation': 45}
    ]

    jgw_file = 'example.jgw'
    xml_file = 'example.xml'

    return regions, jgw_file, xml_file

def run_test():
    """
    Set up and execute the test using the test data.
    """
    regions, jgw_file, xml_file = get_test_data()

    # Parse JGW file
    jgw_params = parse_jgw(jgw_file)

    # Process the regions
    for region in regions:
        initial_x = region['initial_x']
        initial_y = region['initial_y']
        center = region['center']
        height = region['height']
        rotation_angle = region['rotation']

        # Convert the region's initial coordinates to georeferenced coordinates
        x_geo, y_geo = pixel_to_geo_with_transform(initial_x, initial_y, jgw_params, center=center, height=height, rotation_angle=rotation_angle)

        # Output the results for the region
        print(f"Region: {region['name']}, Initial Pixel: ({initial_x}, {initial_y}), Geo Coordinates: ({x_geo}, {y_geo})")

    # Optionally save results as GeoJSON
    output_geojson = 'georeferenced_data.json'
    georeferenced_data = {
        'regions': []
    }
    for region in regions:
        initial_x = region['initial_x']
        initial_y = region['initial_y']
        center = region['center']
        height = region['height']
        rotation_angle = region['rotation']

        x_geo, y_geo = pixel_to_geo_with_transform(initial_x, initial_y, jgw_params, center=center, height=height, rotation_angle=rotation_angle)
        georeferenced_data['regions'].append({
            'name': region['name'],
            'pixel': {'x': initial_x, 'y': initial_y},
            'geo': {'x': x_geo, 'y': y_geo}
        })

    # Save the data to a file
    with open(output_geojson, 'w') as f:
        json.dump(georeferenced_data, f, indent=4)

    print(f"Georeferenced data saved to {output_geojson}")

if __name__ == "__main__":
    run_test()