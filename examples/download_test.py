import geopandas as gpd
import random
import importlib
from shapely.geometry import box
from pathlib import Path

from orthophotos_downloader.data_scraping.image_download import RGBIImageDownloader

# Load the GeoJSON of German federal states and reproject to EPSG:25832 (ETRS89 / UTM zone 32N in meters)
url = "https://raw.githubusercontent.com/isellsoap/deutschlandGeoJSON/main/2_bundeslaender/4_niedrig.geo.json"
gdf = gpd.read_file(url).to_crs("EPSG:25832")

TILE_SIZE = 1000  # Tile size in meters (1x1 km)


# Generate a random tile completely inside the polygon, with a 500 m inner buffer
def random_tile_within(poly, size=100, buffer=500, max_tries=1000):
    inner = poly.buffer(-buffer)  # Apply negative buffer to avoid edge tiles
    if inner.is_empty:
        return None
    minx, miny, maxx, maxy = inner.bounds
    for _ in range(max_tries):
        x = random.uniform(minx, maxx - size)
        y = random.uniform(miny, maxy - size)
        tile = box(x, y, x + size, y + size)
        if inner.contains(tile):
            return tile
    return None  # No valid tile found after max_tries


# Create base output directory for results
BASE_PATH = Path("./examples/data/test_rgbi_results")
BASE_PATH.mkdir(exist_ok=True)

# Iterate through each German state and test RGBI image download
for _, row in gdf.iterrows():
    rgb_dl = None
    cir_dl = None
    result_rgb = None
    result_cir = None
    result = None
    state_name = row["name"]
    print(f"\n--- {state_name} ---")

    # Generate one random test tile per state
    tile = random_tile_within(row.geometry)
    if tile is None:
        print("❌ No valid test tile found.")
        continue

    # Extract the state code (e.g., "HE" from "DE-HE")
    id = row["id"].split("-")[-1]
    rgb_function_name = f"{id}_RGB_Dop20_ImageDownloader"
    cir_function_name = f"{id}_CIR_Dop20_ImageDownloader"

    # Dynamically load the WMS downloader classes from the module
    mod = importlib.import_module("orthophotos_downloader.data_scraping.wms_germany")

    # Wrap the tile geometry in a GeoSeries with the correct CRS
    gdf_tile = gpd.GeoSeries([tile], crs="EPSG:25832")

    # Create a subdirectory for this state's output
    state_path = BASE_PATH / state_name.replace("/", "_")
    state_path.mkdir(exist_ok=True)

    # Download RGB, CIR and RGBI images
    try:
        rgb_dl_class = getattr(mod, rgb_function_name)
        # Instantiate the downloaders with the specified tile size
        rgb_dl = rgb_dl_class(grid_spacing=TILE_SIZE)
        result_rgb = rgb_dl.download_images_from_polygon(
            area_name=state_name,
            area_polygon=gdf_tile,
            out_path=state_path,
            filename_prefix="RGB",
        )
    except Exception as e:
        print(f"❌ RGB download failed in {state_name}: {e}")
        result_rgb = None

    try:
        cir_dl_class = getattr(mod, cir_function_name)
        # Instantiate the downloaders with the specified tile size
        cir_dl = cir_dl_class(grid_spacing=TILE_SIZE)
        result_cir = cir_dl.download_images_from_polygon(
            area_name=state_name,
            area_polygon=gdf_tile,
            out_path=state_path,
            filename_prefix="CIR",
        )
    except Exception as e:
        print(f"❌ CIR download failed in {state_name}: {e}")
        result_cir = None

    if rgb_dl and cir_dl:
        try:
            # Create the RGBI downloader using both RGB and CIR downloaders
            rgbi_dl = RGBIImageDownloader(rgb_dl, cir_dl)
            # Download and merge RGBI images
            result = rgbi_dl.download_rgbi_images_from_polygon(
                area_name=state_name, area_polygon=gdf_tile, out_path=state_path
            )
        except Exception as e:
            print(f"❌ RGBI merge failed in {state_name}: {e}")
            result = None
    else:
        print(f"⚠️ Skipping RGBI merge in {state_name} due to missing RGB or CIR.")

    # Log success
    if result_rgb:
        print(f"✅ {state_name}: {len(result_rgb.images)} RGB images saved.")
    if result_cir:
        print(f"✅ {state_name}: {len(result_cir.images)} CIR images saved.")
    if result:
        print(f"✅ {state_name}: {len(result.images)} RGBI images saved.")
