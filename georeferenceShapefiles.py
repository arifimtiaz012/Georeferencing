import os
import geopandas as gpd
import rasterio
import numpy as np
from rasterio.features import geometry_mask
from shapely.geometry import mapping
from rasterio.transform import from_origin
from rasterio.enums import Resampling
from shapely.geometry import Polygon, Point, LineString


def shapefile_to_raster(shapefile_path, output_raster_path, width, height, transform, crs):
    # Load shapefile
    shapefile = gpd.read_file(shapefile_path)
    print(f"Processing shapefile: {shapefile}")

    # Initialize an empty image (black image)
    image = np.zeros((height, width), dtype=np.uint8)

    # Convert shapefile geometries into a mask and add them to the image
    for geom in shapefile.geometry:
        mask = geometry_mask([geom], transform=transform, invert=True, out_shape=(height, width))
        image[mask] = 255  # You can adjust the pixel value (255 is white)

    # Save the image to a file
    with rasterio.open(output_raster_path, 'w', driver='GTiff', count=1, dtype='uint8',
                       width=width, height=height, crs=crs, transform=transform) as dst:
        dst.write(image, 1)

    print(f"Raster image created at {output_raster_path}")


def get_image_gcp_coords(shapefile_path, transform):
    # Load the shapefile
    shapefile = gpd.read_file(shapefile_path)
    
    # Initialize GCPs list
    gcp_coords = []
    image_coords = []

    for geom in shapefile.geometry:
        if isinstance(geom, Point):  # Handle Point geometries
            lat, lon = geom.y, geom.x
            gcp_coords.append((lat, lon))

            # Convert lat, lon to image pixel coordinates using the transform
            px, py = ~transform * (lon, lat)
            image_coords.append((px, py))
        
        elif isinstance(geom, LineString):  # Handle LineString geometries
            # For LineStrings, sample a few points along the line or just take the endpoints
            for coord in geom.coords:
                lat, lon, *rest = coord  # Unpack and ignore the z-coordinate
                gcp_coords.append((lat, lon))

                # Convert lat, lon to image pixel coordinates using the transform
                px, py = ~transform * (lon, lat)
                image_coords.append((px, py))

        elif isinstance(geom, Polygon):  # Handle Polygon geometries
            # For Polygons, we can take the centroid or sample points along the boundary
            centroid = geom.centroid
            lat, lon = centroid.y, centroid.x
            gcp_coords.append((lat, lon))

            # Convert lat, lon to image pixel coordinates using the transform
            px, py = ~transform * (lon, lat)
            image_coords.append((px, py))

            # Optionally, you can also sample points along the boundary (not just the centroid)
            # If needed, you can uncomment the following loop to include boundary points:
            # for coord in geom.exterior.coords:
            #     lat, lon, *rest = coord  # Unpack and ignore the z-coordinate
            #     gcp_coords.append((lat, lon))
            #     px, py = ~transform * (lon, lat)
            #     image_coords.append((px, py))
    
    print(f"GCP coordinates (lat, lon): {gcp_coords}")
    return gcp_coords, image_coords



def georeference_raster_with_gcp(image_path, gcp_coords, output_image_path):
    with rasterio.open(image_path) as src:
        # Get metadata and setup the transform and CRS
        metadata = src.meta
        transform = src.transform
        crs = src.crs

        # Generate new transformed coordinates based on GCPs (this is just an example approach)
        # Ideally, you should apply a transformation method (like affine transformation or using GCPs in GDAL)
        gcp_x, gcp_y = zip(*gcp_coords)

        # Here, we assume a simple method where GCP coordinates correspond to new georeferenced pixel values
        # Ideally, you'd apply a full GCP-based georeferencing method here
        print("Georeferencing is not yet fully implemented. Placeholder function used.")

        # Save the georeferenced image
        with rasterio.open(output_image_path, 'w', **metadata) as dst:
            dst.write(src.read())

    print(f"Georeferenced image saved to {output_image_path}")


def georeference_directory(directory):
    for filename in os.listdir(directory):
        if filename.endswith('.shp'):
            shapefile_path = os.path.join(directory, filename)
            
            # Example of image generation (You may need to adjust width, height, and transform based on your data)
            output_raster_path = os.path.splitext(shapefile_path)[0] + '_raster.tif'
            
            # Set these according to the bounding box of your shapefile or the desired resolution
            width, height = 1000, 1000  # Adjust these values
            transform = from_origin(-180, 90, 0.1, 0.1)  # Set proper transformation values
            crs = 'EPSG:4326'  # Assuming the shapefile is in WGS84

            # Convert shapefile to raster
            shapefile_to_raster(shapefile_path, output_raster_path, width, height, transform, crs)
            
            # Get Ground Control Points (GCPs) and image coordinates
            gcp_coords, image_coords = get_image_gcp_coords(shapefile_path, transform)
            
            # If you have a corresponding base image to georeference:
            output_georeferenced_image = os.path.splitext(output_raster_path)[0] + '_georeferenced.tif'
            
            # Georeference the generated raster image
            georeference_raster_with_gcp(output_raster_path, gcp_coords, output_georeferenced_image)


if __name__ == "__main__":
    # Specify the directory containing your shapefiles
    directory = r'C:\Users\Arif\Downloads\Download_shapefile+data_2646770 - Copy\open-map-local_5776543'
    outputPath = r'C:\Users\Arif\Downloads\Download_shapefile+data_2646770 - Copy\open-map-local_5776543\output'
    
    # Process the shapefiles in the directory
    print(f"Saving to {outputPath}")
    georeference_directory(directory)
