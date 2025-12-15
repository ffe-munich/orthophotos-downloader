#!/usr/bin/env python3
"""
Universal City Orthophoto Downloader
====================================
Lädt Orthophotos für beliebige Städte/Regionen herunter.
"""

import sys
from pathlib import Path
sys.path.insert(0, 'src')

import geopandas as gpd
from shapely.geometry import box
import logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(message)s')

from orthophotos_downloader.data_scraping.auto_downloader import auto_download_orthophotos

# STANDARD-EINSTELLUNGEN
GRID_SPACING = 600  # Konservativ für alle WMS-Services (max 3000px bei 0.2m Auflösung)
IMAGE_TYPE = 'RGB'

def download_city_orthophotos(city_name, west, south, east, north):
    """
    Lädt Orthophotos für eine beliebige Stadt/Region herunter.
    
    Args:
        city_name: Name der Stadt (für Output-Verzeichnis)
        west, south, east, north: Bounding Box Koordinaten in EPSG:25832
    """
    print(f"📍 {city_name} Orthophoto Download")
    print("=" * 50)
    print(f"🗺️  Koordinaten: {west}, {south}, {east}, {north}")
    
    # Create bounding box and area
    bbox = box(west, south, east, north)
    area_gdf = gpd.GeoDataFrame([1], geometry=[bbox], crs="EPSG:25832")
    
    # Create output directory
    safe_name = city_name.lower().replace(' ', '_').replace('ä', 'ae').replace('ö', 'oe').replace('ü', 'ue')
    output_dir = Path(f"./{safe_name}_orthophotos")
    output_dir.mkdir(exist_ok=True)
    
    print(f"💾 Output: {output_dir}")
    print(f"🔧 Grid: {GRID_SPACING}m | Type: {IMAGE_TYPE}")
    
    try:
        print("🚀 Downloading...")
        results = auto_download_orthophotos(
            area_name=f"{safe_name}_download",
            area_polygon=area_gdf.geometry,
            out_path=output_dir,
            grid_spacing=GRID_SPACING,
            image_type=IMAGE_TYPE,
            filename_prefix="ortho"
        )
        
        # Show results
        total = sum(len(dataset.images) for dataset in results.values())
        print(f"✅ {total} Bilder heruntergeladen")
        for state, dataset in results.items():
            print(f"📊 {state}: {len(dataset.images)} Bilder")
        
        return True
    except Exception as e:
        print(f"❌ Fehler: {e}")
        return False

def main():
    """Hauptfunktion für Kommandozeilen-Nutzung."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Universal City Orthophoto Downloader")
    parser.add_argument("city_name", help="Name der Stadt/Region")
    parser.add_argument("west", type=float, help="West-Koordinate (EPSG:25832)")
    parser.add_argument("south", type=float, help="Süd-Koordinate (EPSG:25832)")
    parser.add_argument("east", type=float, help="Ost-Koordinate (EPSG:25832)")
    parser.add_argument("north", type=float, help="Nord-Koordinate (EPSG:25832)")
    
    args = parser.parse_args()
    
    success = download_city_orthophotos(
        args.city_name, 
        args.west, 
        args.south, 
        args.east, 
        args.north
    )
    
    if success:
        print("\n🎯 Visualisieren Sie die Ergebnisse mit:")
        print("python simple_visualize_tiffs.py")

if __name__ == "__main__":
    if len(sys.argv) == 1:
        print("🌍 Universal City Orthophoto Downloader")
        print("=" * 50)
        print("Usage: python download_city.py <city_name> <west> <south> <east> <north>")
        print("\nBeispiele:")
        print("python download_city.py Lausingen 470000 5542000 471000 5543000")
        print("python download_city.py Tübingen 515000 5410000 520000 5415000")
        print("\n💡 Koordinaten in EPSG:25832 (UTM Zone 32N)")
        print("💡 Finden Sie Koordinaten auf: https://epsg.io/25832")
    else:
        main()
