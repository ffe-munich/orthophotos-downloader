#!/usr/bin/env python3
"""
Ultra-Simplified TIFF Visualization Script (< 100 lines)
Visualizes orthophoto TIFF files in a grid layout.
"""
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import rasterio
import numpy as np

def visualize_tiffs(directory, max_images=9):
    """Visualize TIFF files from directory in grid layout."""
    # Find TIFF files
    tiff_files = sorted(list(Path(directory).rglob("*.tiff")) + list(Path(directory).rglob("*.tif")))
    
    if not tiff_files:
        print(f"❌ No TIFF files in {directory}")
        return
    
    # Limit files and calculate grid
    files = tiff_files[:max_images]
    n = len(files)
    cols = int(np.ceil(np.sqrt(n)))
    rows = int(np.ceil(n / cols))
    
    print(f"📷 Showing {n} of {len(tiff_files)} TIFF files from {Path(directory).name}")
    
    # Create figure
    fig, axes = plt.subplots(rows, cols, figsize=(15, 12))
    fig.suptitle(f'Orthophotos: {Path(directory).name}', fontsize=16)
    
    # Handle single image case
    if n == 1:
        axes = [axes]
    elif rows == 1:
        axes = axes if hasattr(axes, '__len__') else [axes]
    else:
        axes = axes.flatten()
    
    # Display each image
    for i, tiff_file in enumerate(files):
        try:
            with rasterio.open(tiff_file) as src:
                image = src.read()
                
                # Convert to RGB for display
                if image.shape[0] >= 3:  # RGB+
                    display_img = np.transpose(image[:3], (1, 2, 0))
                    display_img = np.clip(display_img / display_img.max(), 0, 1)
                else:  # Grayscale
                    display_img = image[0]
                
                axes[i].imshow(display_img, cmap='gray' if image.shape[0] == 1 else None)
                axes[i].set_title(f'{tiff_file.name}\n{src.width}×{src.height}px', fontsize=8)
                axes[i].axis('off')
                
        except Exception as e:
            axes[i].text(0.5, 0.5, f'Error:\n{tiff_file.name}', ha='center', va='center')
            axes[i].axis('off')
    
    # Hide unused subplots
    for i in range(n, len(axes)):
        axes[i].axis('off')
    
    plt.tight_layout()
    plt.show()

def main():
    """Main function with automatic path detection."""
    # Priority search paths (Ulm first, then Mainz)
    search_paths = [
        "./ulm_multi_state_test", 
        "./ulm_orthophotos",
        "./mainz_bbox_test",
        "./mainz_orthophotos"
    ]
    
    if len(sys.argv) > 1:
        directory = sys.argv[1]
    else:
        directory = None
        for path in search_paths:
            if Path(path).exists() and list(Path(path).rglob("*.tif*")):
                directory = path
                break
        
        if not directory:
            print("❌ No TIFF directories found! Run download_city.py first")
            return
    
    visualize_tiffs(directory)

if __name__ == "__main__":
    main()
