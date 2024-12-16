import os
import glob
import json
import math
import pyproj
import xml.etree.ElementTree as ET

'''
Assumptions made:
- The JPW file is in the same directory as the JPEG file.
- The XML file is in the same directory as the JPEG file.
- The JPW file contains the following parameters in the following order: pixel_size_x, rotation_x, rotation_y, pixel_size_y, upper_left_x, upper_left_y.
- The XML file contains the following fields: copyright, km_reference, date_flown, coordinates, lens_focal_length, resolution.
- From srsName="osgb:BNG" in XML, assuming that we are using british national grid coordinate system by default. 
    This script just converts it to latitude, longitude at the end. 

    If we want to georeference using lat,lon to begin with, we either convert to BNG at the start or add separate logic for lat,lon.
    Defined box is lost upon georeferencing. Did not add anything currently to prevent this as it would mean having more than lat, lon coordinates.

Current status: Needs some data to test it on.
                Directory needs to be manually set in line 222.
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

def parse_jpw(jpw_file):
    """
    Parse the JPW file and extract transformation parameters.

    Returns: pixel_size_x, rotation_x, rotation_y, pixel_size_y, upper_left_x, upper_left_y.
    - upper_left values are the coordinates of the upper-left corner of the image.
    - pixel_size values are the scale factors for the x and y directions.
    - rotation is the angle of rotation of the image. In our case there is no rotation, but this is included for scalability purposes
        rotation: rotation_x == rotation_y. (value of either indicates rotation angle)
        skewed: rotation_x != rotaion_y.
    """
    with open(jpw_file, 'r') as f:
        jpw = [float(line.strip()) for line in f.readlines()]

    pixel_size_x = jpw[0]  # Pixel size in x-direction (width of a single pixel in the coordinate space)
    # E.g. (pixel_size_x == 0.25) means that each pixel in the image represents 0.25 units (meters) in the coordinate space
 
    rotation_x = jpw[1]    # Rotation (x-axis)
    rotation_y = jpw[2]    # Rotation (y-axis)
    pixel_size_y = jpw[3]  # Pixel size in y-direction (negative for north-up)
    upper_left_x = jpw[4]  # Upper-left x-coordinate
    upper_left_y = jpw[5]  # Upper-left y-coordinate

    return pixel_size_x, rotation_x, rotation_y, pixel_size_y, upper_left_x, upper_left_y


def pixel_to_geo(pixel_x, pixel_y, jpw_params):
    """
    Auxiliarry function:
    Converts pixel coordinates to georeferenced coordinates using JPW parameters.
    """
    pixel_size_x, rotation_x, rotation_y, pixel_size_y, upper_left_x, upper_left_y = jpw_params

    # (Regular distance) + (Rotation accounted distance) + (Upper left corner starting point)
    x_geo = (pixel_x * pixel_size_x) + (pixel_y * rotation_x) + upper_left_x
    y_geo = (pixel_y * pixel_size_y) + (pixel_x * rotation_y) + upper_left_y

    return x_geo, y_geo


def pixel_to_geo_with_transform(pixel_x, pixel_y, jpw_params, center=None, height=None, width=None, rotation_angle=0):
    """
    Convert pixel coordinates to georeferenced coordinates, considering optional rotation, scaling, and translation.

    Args:
        pixel_x, pixel_y: Initial pixel coordinates.
        jpw_params: Parameters from the JPW file (scale, rotation, offsets).
        center: Tuple of (center_x, center_y) for the rotation center (optional).
        height: Height of the bounding box in pixels (optional).
        width: Width of the bounding box in pixels (defaults to height if not provided, optional).
        rotation_angle: Rotation angle in degrees (clockwise) about the center (optional).

    Returns:
        x_geo, y_geo: Transformed georeferenced coordinates.
    """
    # If no center or height/width, treat as a single pixel
    if center is None or height is None:
        return pixel_to_geo(pixel_x, pixel_y, jpw_params)

    # Otherwise, treat as a box and apply transformations
    pixel_size_x, rotation_x, rotation_y, pixel_size_y, upper_left_x, upper_left_y = jpw_params
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

    # Convert pixel coordinates to georeferenced coordinates using JPW
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


def process_directory(directory):
    """
    Process a directory containing JPEG, JPW, and optional XML files.
    """
    # Find all JPEG files in the directory
    jpeg_files = glob.glob(os.path.join(directory, '*.jpg'))

    for jpeg_file in jpeg_files:
        # Find the corresponding JPW and XML file paths
        base_name = os.path.splitext(jpeg_file)[0]
        jpw_file = base_name + '.jpw'
        xml_file = base_name + '.xml'

        if not os.path.exists(jpw_file):
            print(f"Skipping {jpeg_file}: Missing JPW file.")
            continue

        # Parse JPW file
        jpw_params = parse_jpw(jpw_file)

        # Parse optional XML metadata
        metadata = parse_xml_metadata(xml_file)

        # Example: Process pixel regions or specific pixel coordinates
        regions = [
            {'name': 'center', 'pixel_x': 500, 'pixel_y': 500},
            {'name': 'top_left', 'pixel_x': 0, 'pixel_y': 0},
            {'name': 'bottom_right', 'pixel_x': 1000, 'pixel_y': 1000}
        ]

        # Convert each pixel region to geo-coordinates
        for region in regions:
            pixel_x = region['pixel_x']
            pixel_y = region['pixel_y']
            x_geo, y_geo = pixel_to_geo_with_transform(pixel_x, pixel_y, jpw_params)

            print(f"Image: {jpeg_file}, Region: {region['name']}, Pixel: ({pixel_x}, {pixel_y}), Geo: ({x_geo}, {y_geo})")

        # Optionally save metadata and georeferenced results
        output_geojson = base_name + '_georeferenced.json'
        georeferenced_data = {
            'image': jpeg_file,
            'jpw_file': jpw_file,
            'regions': []
        }
        for region in regions:
            pixel_x = region['pixel_x']
            pixel_y = region['pixel_y']
            x_geo, y_geo = pixel_to_geo_with_transform(pixel_x, pixel_y, jpw_params)
            georeferenced_data['regions'].append({
                'name': region['name'],
                'pixel': {'x': pixel_x, 'y': pixel_y},
                'geo': {'x': x_geo, 'y': y_geo}
            })

        if metadata:
            georeferenced_data['metadata'] = metadata

        with open(output_geojson, 'w') as f:
            json.dump(georeferenced_data, f, indent=4)

        print(f"Georeferenced data saved to {output_geojson}")


if __name__ == "__main__":
    # Directory containing JPEG, JPW, and XML files.
    directory = r'C:\path\to\your\directory'
    process_directory(directory)
