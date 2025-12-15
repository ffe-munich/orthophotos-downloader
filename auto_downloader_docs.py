"""
Auto Orthophoto Downloader - Python Documentation
================================================

This module provides the AutoOrthophotoDownloader functionality that automatically 
detects which WMS services are needed for a given area and downloads orthophotos 
from all relevant services.

Problem Solved:
--------------
Previously, users had to manually:
1. Determine which German federal states their area of interest covers
2. Instantiate the correct WMS downloader for each state
3. Split their area polygon by state boundaries
4. Download from each service separately

The AutoOrthophotoDownloader automates this entire process.

Quick Start Examples:
===================

Simple Usage (Convenience Function):
-----------------------------------
"""

def example_simple_usage():
    """
    Example of simple usage with the convenience function.
    
    This example shows how to automatically download RGB orthophotos
    for any area that may span multiple German federal states.
    """
    import geopandas as gpd
    from pathlib import Path
    from orthophotos_downloader import auto_download_orthophotos

    # Load your area of interest
    area = gpd.read_file('my_area.geojson')

    # Automatically download RGB orthophotos
    results = auto_download_orthophotos(
        area_name="my_area",
        area_polygon=area.geometry,
        out_path=Path("./downloads"),
        grid_spacing=1000,  # 1km tiles
        image_type="RGB"    # or "CIR" or "RGBI"
    )

    # Results is a dictionary mapping state names to AreaDataset objects
    for state_name, area_dataset in results.items():
        print(f"{state_name}: {len(area_dataset.images)} images downloaded")


def example_advanced_usage():
    """
    Example of advanced usage with the class-based approach.
    
    This example shows how to use the AutoOrthophotoDownloader class
    directly for more control over the download process.
    """
    from orthophotos_downloader import AutoOrthophotoDownloader
    import geopandas as gpd
    from pathlib import Path

    # Load your area of interest
    area = gpd.read_file('my_area.geojson')

    # Create auto downloader instance
    auto_downloader = AutoOrthophotoDownloader(grid_spacing=1000)

    # First, see which states intersect with your area
    intersecting_states = auto_downloader.detect_intersecting_states(area.geometry)
    for state_name, state_code, intersection_geom in intersecting_states:
        print(f"Found intersection with {state_name} ({state_code})")

    # Download RGB images
    rgb_results = auto_downloader.download_rgb_images_auto(
        area_name="my_area",
        area_polygon=area.geometry,
        out_path=Path("./downloads/rgb"),
        filename_prefix="rgb"
    )

    # Download CIR images (if available)
    cir_results = auto_downloader.download_cir_images_auto(
        area_name="my_area",
        area_polygon=area.geometry,
        out_path=Path("./downloads/cir"),
        filename_prefix="cir"
    )

    # Download and merge RGBI images
    rgbi_results = auto_downloader.download_rgbi_images_auto(
        area_name="my_area",
        area_polygon=area.geometry,
        out_path=Path("./downloads/rgbi")
    )


def example_cross_border_area():
    """
    Example of downloading orthophotos for an area that crosses state borders.
    
    This example creates a test area that spans multiple German federal states
    and demonstrates how the auto downloader handles this automatically.
    """
    import geopandas as gpd
    from pathlib import Path
    from shapely.geometry import box
    from orthophotos_downloader import AutoOrthophotoDownloader

    # Create a test area that spans Bavaria and Baden-Württemberg border
    # Area around Ulm/Neu-Ulm (coordinates in EPSG:25832)
    test_area_bbox = box(570000, 5370000, 580000, 5380000)  # 10km x 10km area
    test_area = gpd.GeoDataFrame([1], geometry=[test_area_bbox], crs="EPSG:25832")

    # Create auto downloader
    auto_downloader = AutoOrthophotoDownloader(grid_spacing=2000)  # 2km tiles

    # Detect which states intersect with our area
    intersecting_states = auto_downloader.detect_intersecting_states(test_area.geometry)
    
    print(f"Found {len(intersecting_states)} intersecting states:")
    for state_name, state_code, intersection_geom in intersecting_states:
        area_km2 = intersection_geom.area / 1000000
        print(f"  - {state_name} ({state_code}): {area_km2:.2f} km²")

    # Download RGB orthophotos automatically
    results = auto_downloader.download_rgb_images_auto(
        area_name="cross_border_test",
        area_polygon=test_area.geometry,
        out_path=Path("./cross_border_downloads"),
        filename_prefix="test_rgb"
    )

    # Show results
    total_images = 0
    for state_name, area_dataset in results.items():
        num_images = len(area_dataset.images)
        total_images += num_images
        print(f"{state_name}: {num_images} images downloaded")
    
    print(f"Total images downloaded: {total_images}")
    
    # Automatische Erkennung und Download von Orthophotos über Bundesländergrenzen hinweg
    # Diese Funktion zeigt, wie das System automatisch mehrere WMS-Dienste verwendet


def example_migration_from_manual():
    """
    Example showing how to migrate from manual approach to automatic approach.
    
    This example compares the old manual way with the new automatic way.
    """
    # OLD MANUAL APPROACH (you had to know this was Bavaria)
    # from orthophotos_downloader.data_scraping.wms_germany import BayernDop20ImageDownloader
    # downloader = BayernDop20ImageDownloader(grid_spacing=1000)
    # result = downloader.download_images_from_polygon(...)

    # NEW AUTOMATIC APPROACH (works for any area)
    from orthophotos_downloader import auto_download_orthophotos
    from pathlib import Path
    import geopandas as gpd

    # Load your area (can be anywhere in Germany)
    area = gpd.read_file('my_area.geojson')

    # Automatically detects which states are needed and downloads from all
    results = auto_download_orthophotos(
        area_name="my_area",
        area_polygon=area.geometry,
        out_path=Path("./downloads"),
        grid_spacing=1000
    )

    print("The auto downloader is backward compatible - you can still use the manual approach if needed.")


def example_different_image_types():
    """
    Example showing how to download different image types.
    
    This example demonstrates downloading RGB, CIR, and RGBI images.
    """
    from orthophotos_downloader import auto_download_orthophotos
    from pathlib import Path
    import geopandas as gpd

    # Load your area
    area = gpd.read_file('my_area.geojson')
    base_path = Path("./image_type_downloads")

    # Download RGB images
    rgb_results = auto_download_orthophotos(
        area_name="my_area",
        area_polygon=area.geometry,
        out_path=base_path / "rgb",
        image_type="RGB"
    )

    # Download CIR images (Color Infrared)
    try:
        cir_results = auto_download_orthophotos(
            area_name="my_area",
            area_polygon=area.geometry,
            out_path=base_path / "cir",
            image_type="CIR"
        )
    except Exception as e:
        print(f"CIR download failed: {e}")
        print("This may be because CIR images are not available for all states.")

    # Download RGBI images (RGB + Infrared merged)
    try:
        rgbi_results = auto_download_orthophotos(
            area_name="my_area",
            area_polygon=area.geometry,
            out_path=base_path / "rgbi",
            image_type="RGBI"
        )
    except Exception as e:
        print(f"RGBI download failed: {e}")
        print("This may be because CIR images are not available for all states.")


def example_with_mask():
    """
    Example showing how to use a mask to limit downloads to specific areas.
    
    This example demonstrates using a building mask to only download
    orthophotos in areas that contain buildings.
    """
    from orthophotos_downloader import auto_download_orthophotos
    from pathlib import Path
    import geopandas as gpd

    # Load your area of interest
    area = gpd.read_file('my_area.geojson')
    
    # Load a mask (e.g., building mask)
    building_mask = gpd.read_file('building_mask.geojson')

    # Download only in areas that overlap with the mask
    results = auto_download_orthophotos(
        area_name="my_area_with_buildings",
        area_polygon=area.geometry,
        out_path=Path("./masked_downloads"),
        grid_spacing=1000,
        image_type="RGB",
        mask=building_mask.geometry,
        buffer_size=100  # 100m buffer around the area
    )

    print(f"Downloaded images only in areas with buildings")


"""
Features:
=========

- Automatic State Detection: Automatically determines which German federal states 
  intersect with your area of interest
- Geometric Intersection: Calculates the exact intersection geometry for each state
- WMS Service Mapping: Automatically maps each state to its corresponding WMS downloader class
- Multi-Service Downloads: Downloads from all relevant WMS services in parallel
- Flexible Input: Accepts Shapely Polygons, GeoSeries, or GeoDataFrames

Supported Image Types:
=====================

1. RGB: Standard red-green-blue orthophotos
2. CIR: Color infrared orthophotos (where available)
3. RGBI: Merged 4-band images combining RGB and infrared channels

Output Structure:
================

The auto downloader organizes downloads by state:

downloads/
├── Bayern/
│   ├── auto_rgb_BY_0001.tiff
│   ├── auto_rgb_BY_0002.tiff
│   └── ...
├── Baden-Württemberg/
│   ├── auto_rgb_BW_0001.tiff
│   ├── auto_rgb_BW_0002.tiff
│   └── ...
└── ...

Requirements:
============

The auto downloader requires:
- geopandas for spatial operations
- shapely for geometry handling
- Internet connection to load German state boundaries (cached after first use)
- Access to German WMS services

Error Handling:
==============

The auto downloader is designed to be robust:
- If a WMS service is unavailable for one state, downloads continue for other states
- Clear error messages indicate which services failed and why
- Partial results are still returned for successful downloads

API Reference:
=============

auto_download_orthophotos() function:
------------------------------------
Convenience function for automatic downloads.

Parameters:
- area_name (str): Name of the area for identification
- area_polygon: Area of interest (Polygon, GeoSeries, or GeoDataFrame)
- out_path (Path): Output directory
- grid_spacing (int): Grid spacing in meters (default: 1000)
- image_type (str): "RGB", "CIR", or "RGBI" (default: "RGB")
- filename_prefix (str, optional): Prefix for filenames
- mask (optional): Mask to limit downloads to specific areas
- buffer_size (int): Buffer size around the area (default: 0)

Returns:
- Dictionary mapping state names to AreaDataset objects

AutoOrthophotoDownloader class:
------------------------------
Main class for automatic orthophoto downloads.

Methods:
- detect_intersecting_states(area_polygon): Detect intersecting German states
- download_rgb_images_auto(...): Download RGB images automatically
- download_cir_images_auto(...): Download CIR images automatically  
- download_rgbi_images_auto(...): Download and merge RGBI images automatically
"""

if __name__ == "__main__":
    print("Auto Orthophoto Downloader Documentation")
    print("========================================")
    print()
    print("This file contains documentation and examples for the AutoOrthophotoDownloader.")
    print("Run the individual example functions to see how to use the functionality.")
    print()
    print("Available examples:")
    print("- example_simple_usage(): Basic usage with convenience function")
    print("- example_advanced_usage(): Advanced usage with class-based approach")
    print("- example_cross_border_area(): Example with area spanning multiple states")
    print("- example_migration_from_manual(): How to migrate from manual approach")
    print("- example_different_image_types(): Download different image types")
    print("- example_with_mask(): Using masks to limit downloads")
    print()
    print("To run an example:")
    print("python auto_downloader_docs.py")
    print(">>> example_simple_usage()")
