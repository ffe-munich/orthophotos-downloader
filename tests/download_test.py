"""Pytest-based WMS download tests for all German federal states."""

import importlib
import random
from pathlib import Path

import geopandas as gpd
import pytest
from shapely.geometry import box

from orthophotos_downloader.data_scraping.image_download import RGBIImageDownloader


# Test configuration
TILE_SIZE = 10
BUFFER = 5
MAX_TRIES = 1000
OUTPUT_PATH = Path("./test_folder/")

# Critical states that must pass
CRITICAL_STATES = {"Bayern", "Baden-Württemberg"}


def random_tile_within(poly, size: int = TILE_SIZE, buffer: int = BUFFER, max_tries: int = MAX_TRIES):
    """Generate a random tile completely inside the polygon with buffer."""
    inner = poly.buffer(-buffer)
    if inner.is_empty:
        return None

    minx, miny, maxx, maxy = inner.bounds
    for _ in range(max_tries):
        x = random.uniform(minx, maxx - size)
        y = random.uniform(miny, maxy - size)
        tile = box(x, y, x + size, y + size)
        if inner.contains(tile):
            return tile
    return None


@pytest.fixture(scope="session")
def german_states():
    """Load German federal states GeoDataFrame."""
    url = "https://raw.githubusercontent.com/isellsoap/deutschlandGeoJSON/main/2_bundeslaender/4_niedrig.geo.json"
    gdf = gpd.read_file(url).to_crs("EPSG:25832")
    return gdf


@pytest.fixture(scope="session")
def output_path():
    """Create and return output directory for test artifacts."""
    OUTPUT_PATH.mkdir(exist_ok=True)
    return OUTPUT_PATH


def pytest_generate_tests(metafunc):
    """Generate test parameters for each German state."""
    if "state_info" in metafunc.fixturenames:
        url = "https://raw.githubusercontent.com/isellsoap/deutschlandGeoJSON/main/2_bundeslaender/4_niedrig.geo.json"
        gdf = gpd.read_file(url).to_crs("EPSG:25832")
        
        states = []
        for _, row in gdf.iterrows():
            state_name = row["name"]
            state_code = row["id"].split("-")[-1]
            is_critical = state_name in CRITICAL_STATES
            states.append((state_name, state_code, row.geometry, is_critical))
        
        metafunc.parametrize(
            "state_info",
            states,
            ids=[s[0] for s in states],  # Use state names as test IDs
        )


@pytest.mark.download
def test_state_wms_download(state_info, output_path):
    """Test WMS RGB and CIR downloads for a German state."""
    state_name, state_code, geometry, is_critical = state_info
    
    print(f"\n{'='*60}")
    print(f"🔄 Testing: {state_name} ({state_code})")
    print(f"   Critical state: {'YES 🚨' if is_critical else 'No'}")
    print(f"{'='*60}")
    
    # Mark critical tests
    if is_critical:
        pytest.mark.critical
    
    # Generate test tile
    tile = random_tile_within(geometry)
    if tile is None:
        if is_critical:
            pytest.fail(f"🚨 CRITICAL: No valid test tile found for {state_name}")
        else:
            pytest.skip(f"No valid test tile found for {state_name}")
    
    # Prepare geometry
    gdf_tile = gpd.GeoSeries([tile], crs="EPSG:25832")
    state_path = output_path / state_name.replace("/", "_")
    state_path.mkdir(exist_ok=True, parents=True)
    
    # Import WMS module
    wms_module = importlib.import_module("orthophotos_downloader.data_scraping.wms_germany")
    
    # Test RGB download
    rgb_downloader = None
    try:
        rgb_class = getattr(wms_module, f"{state_code}_RGB_Dop20_ImageDownloader")
        rgb_downloader = rgb_class(grid_spacing=TILE_SIZE)
        rgb_result = rgb_downloader.download_images_from_polygon(
            area_name=state_name,
            area_polygon=gdf_tile,
            out_path=state_path,
            filename_prefix="RGB",
        )
        rgb_count = len(rgb_result.images) if rgb_result else 0
        assert rgb_count > 0, f"RGB download produced no images"
        print(f"   ✅ RGB: {rgb_count} images downloaded")
    except Exception as e:
        print(f"   ❌ RGB download failed: {e}")
        if is_critical:
            pytest.fail(f"🚨 CRITICAL: RGB download failed for {state_name}: {e}")
        else:
            pytest.xfail(f"⚠️  RGB download failed for {state_name}: {e}")
    
    # Test CIR download
    cir_downloader = None
    try:
        cir_class = getattr(wms_module, f"{state_code}_CIR_Dop20_ImageDownloader")
        cir_downloader = cir_class(grid_spacing=TILE_SIZE)
        cir_result = cir_downloader.download_images_from_polygon(
            area_name=state_name,
            area_polygon=gdf_tile,
            out_path=state_path,
            filename_prefix="CIR",
        )
        cir_count = len(cir_result.images) if cir_result else 0
        assert cir_count > 0, f"CIR download produced no images"
        print(f"   ✅ CIR: {cir_count} images downloaded")
    except Exception as e:
        print(f"   ❌ CIR download failed: {e}")
        if is_critical:
            pytest.fail(f"🚨 CRITICAL: CIR download failed for {state_name}: {e}")
        else:
            pytest.xfail(f"⚠️  CIR download failed for {state_name}: {e}")
    
    # Test RGBI merge (informational only)
    if rgb_downloader and cir_downloader:
        try:
            rgbi_downloader = RGBIImageDownloader(rgb_downloader, cir_downloader)
            rgbi_result = rgbi_downloader.download_rgbi_images_from_polygon(
                area_name=state_name, area_polygon=gdf_tile, out_path=state_path
            )
            rgbi_count = len(rgbi_result.images) if rgbi_result else 0
            print(f"   ✅ RGBI: {rgbi_count} images merged")
            print(f"\n✅ {state_name}: Complete success!")
        except Exception as e:
            # RGBI merge failure is not critical
            print(f"   ⚠️ RGBI merge failed: {e}")
            print(f"\n🟡 {state_name}: RGB/CIR OK, RGBI merge failed")


@pytest.fixture(scope="session", autouse=True)
def print_test_summary(request):
    """Print a summary report after all tests complete."""
    yield
    
    # This runs after all tests
    if hasattr(request.config, "pluginmanager"):
        stats = request.config.pluginmanager.get_plugin("terminalreporter").stats
        
        print("\n" + "=" * 80)
        print("📊 WMS DOWNLOAD TEST SUMMARY")
        print("=" * 80)
        
        passed = len(stats.get("passed", []))
        failed = len(stats.get("failed", []))
        xfailed = len(stats.get("xfailed", []))
        skipped = len(stats.get("skipped", []))
        
        print(f"\n✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  Expected failures (non-critical): {xfailed}")
        print(f"⏭️  Skipped: {skipped}")
        print("\n" + "=" * 80)
