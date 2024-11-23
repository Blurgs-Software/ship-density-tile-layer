from flask import Flask, send_file, jsonify
import dask.dataframe as dd
import numpy as np
import rasterio
from rasterio.transform import from_bounds
import matplotlib.pyplot as plt
from osgeo import gdal
import os
from concurrent.futures import ThreadPoolExecutor
from tqdm import tqdm
from dask.diagnostics import ProgressBar

app = Flask(__name__)

# Load and process data using Dask


attributes = [
    'commercial_value', 'commercial_rarity',
    'fishing_value', 'fishing_rarity',
    'oil_gas_value', 'oil_gas_rarity',
    'passenger_value', 'passenger_rarity',
    'leisure_value', 'leisure_rarity',
    'global_value', 'global_rarity'
]


def draw_rectangle_with_border(raster, top_left_row, bottom_right_row, top_left_col, bottom_right_col, color, border_color):
    min_row, max_row = sorted([top_left_row, bottom_right_row])
    min_col, max_col = sorted([top_left_col, bottom_right_col])
    raster[min_row:max_row, min_col:max_col] = color
    if min_row < max_row and min_col < max_col:
        raster[min_row:max_row, min_col] = border_color
        raster[min_row:max_row, max_col - 1] = border_color
        raster[min_row, min_col:max_col] = border_color
        raster[max_row - 1, min_col:max_col] = border_color

def convert_tif_to_tiles(input_tif, output_dir, zoom_levels='0-3'):
    gdal_command = f"gdal2tiles.py -p raster -z {zoom_levels} {input_tif} {output_dir}"
    os.system(gdal_command)



def generate_raster_for_attribute(attribute, data, west, east, south, north, resolution, width, height):
    values = data[attribute].compute()
    max_value = values.max()
    min_value = values.min()
    color_map = plt.get_cmap('viridis')

    # Initialize raster
    raster = np.zeros((height, width, 3), dtype=np.uint8)
    base_dir = './data'
    os.makedirs(base_dir, exist_ok=True)

    filename = os.path.join(base_dir, f'{attribute}.tif')
    tile_output_dir = os.path.join(base_dir, f"tiles_{attribute}")
    os.makedirs(tile_output_dir, exist_ok=True)

    # Function to process a single chunk
    def process_chunk(chunk):
        chunk_raster = np.zeros_like(raster)  # Local raster for the chunk
        df = chunk.compute()
        for index, row in df.iterrows():
            top_left_row = int((row['top_left_lat'] - south) / resolution)
            bottom_right_row = int((row['bottom_right_lat'] - south) / resolution)
            top_left_col = int((row['top_left_lon'] - west) / resolution)
            bottom_right_col = int((row['bottom_right_lon'] - west) / resolution)
            if max_value != min_value:
                normalized_value = (row[attribute] - min_value) / (max_value - min_value)
            else:
                normalized_value = 0.0

            color = np.array(color_map(normalized_value)[:3]) * 255
            color = color.astype(np.uint8)
            border_color = np.array([255, 0, 0]) if normalized_value < 0.5 else np.array([0, 255, 0])
            draw_rectangle_with_border(chunk_raster, top_left_row, bottom_right_row, top_left_col, bottom_right_col, color, border_color)
        return chunk_raster

    # Use ThreadPoolExecutor to parallelize chunk processing
    chunks = list(data.to_delayed())
    with ThreadPoolExecutor() as executor, tqdm(total=len(chunks), desc="Processing Chunks") as pbar:
        chunk_rasters = []
        for result in executor.map(process_chunk, chunks):
            chunk_rasters.append(result)
            pbar.update(1)

    # Combine all chunk rasters into the main raster
    for chunk_raster in chunk_rasters:
        raster += chunk_raster

    # Save the raster to a GeoTIFF
    transform = from_bounds(west, south, east, north, width, height)
    with rasterio.open(
        filename, 'w', driver='GTiff',
        height=height, width=width, count=3,
        dtype=raster.dtype, crs='EPSG:4326', transform=transform
    ) as dst:
        dst.write(raster.transpose(2, 0, 1))

    # Convert the GeoTIFF to tiles
    convert_tif_to_tiles(filename, tile_output_dir)




@app.route('/generate_all_tiles')
def generate_all_tiles():
    print("Starting the tile generation process.")
    
    # Path to the CSV file
    csv_file_path = os.environ.get('CSV_FILE_PATH', '/data/your_dataset.csv')
    print(f"CSV file path: {csv_file_path}")
    
    if not os.path.exists(csv_file_path):
        print("CSV file not found. Exiting process.")
        raise FileNotFoundError(f"CSV file not found at {csv_file_path}")
    
    print("Reading the CSV file into a Dask DataFrame.")
    data = dd.read_csv(csv_file_path, assume_missing=True)
    
    # Enable ProgressBar for initial computation
    print("Loading and persisting the DataFrame into memory. Progress bar enabled.")
    with ProgressBar():
        data = data.persist()  # Triggers computation and caching

    print("Computing bounding box coordinates.")
    west = data['top_left_lon'].min().compute()
    east = data['bottom_right_lon'].max().compute()
    south = data['bottom_right_lat'].min().compute()
    north = data['top_left_lat'].max().compute()
    print(f"Bounding box computed: West={west}, East={east}, South={south}, North={north}")
    
    # Define resolution and calculate raster dimensions
    resolution = 0.01  # Adjust for finer detail or performance
    width = int((east - west) / resolution)
    height = int((north - south) / resolution)
    print(f"Raster dimensions calculated: Width={width}, Height={height}, Resolution={resolution}")
    
    for attribute in attributes:
        print(f"Starting raster generation for attribute: {attribute}")
        generate_raster_for_attribute(attribute, data, west, east, south, north, resolution, width, height)
        print(f"Raster generation completed for attribute: {attribute}")
    
    print("Tile generation process completed for all attributes.")
    return jsonify({"message": "Raster and tiles generated for all attributes"}), 200


@app.route('/tiles/<attribute>/<int:z>/<int:x>/<int:y>.png')
def get_tile(attribute, z, x, y):
    # Build the complete file path for the requested tile
    tile_path = os.path.join('data', f"tiles_{attribute}", f"{z}", f"{x}", f"{y}.png")
    try:
        return send_file(tile_path, mimetype='image/png')
    except FileNotFoundError:
        return "Tile not found", 404
    
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8000))  # Use PORT from environment
    app.run(host='0.0.0.0', port=port)  # Bind to 0.0.0.0


