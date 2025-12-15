# Multi-State Orthophoto Downloader Implementation

## Overview
This pull request implements comprehensive multi-state (cross-border) orthophoto download functionality for the orthophotos-downloader project. The implementation automatically detects intersecting German federal states and handles downloads from multiple WMS services seamlessly.

## 🚀 New Features

### 1. AutoOrthophotoDownloader Class
- **Automatic State Detection**: Automatically identifies which German federal states intersect with the area of interest
- **Multi-Service Coordination**: Handles downloads from multiple WMS services (one per detected state)
- **Cross-Border Support**: Seamlessly processes areas that span multiple states (e.g., Ulm/Neu-Ulm crossing Baden-Württemberg and Bayern)
- **Unified Output**: Provides consistent folder structure and file naming across all states

### 2. Convenience Function
- `auto_download_orthophotos()`: High-level function for simple one-line downloads
- Automatic area naming and path management
- Support for all image types (RGB, CIR, RGBI)

### 3. Comprehensive Documentation
- Complete Python API documentation with examples
- Detailed docstrings for all classes and methods
- Usage patterns for different scenarios (single state, multi-state, cross-border)

## 🧪 Testing & Validation

### Multi-State Testing Coverage
✅ **Single State Areas**:
- Mainz (Hessen) - confirmed single state detection and download
- München (Bayern) - validated proper coordinate handling and image retrieval

✅ **Cross-Border Areas**:
- Ulm/Neu-Ulm - spans Baden-Württemberg and Bayern
- Automatic detection of both states
- Verified downloads from both WMS services
- Consistent file organization and naming

✅ **Coordinate System Support**:
- EPSG:25832 (UTM Zone 32N) coordinates validated
- Proper bounding box handling across state boundaries
- Coordinate transformation verification

### Visualization Pipeline
✅ **Enhanced Visualization Script** (`simple_visualize_tiffs.py`):
- Automatic path detection and traversal
- Multi-state folder structure support
- Robust TIFF file handling
- State-wise visualization with proper subplot organization

## 📁 Key Files Added/Modified

### New Core Implementation
- `src/orthophotos_downloader/data_scraping/auto_downloader.py` - Main AutoOrthophotoDownloader class
- `auto_downloader_docs.py` - Comprehensive API documentation and examples

### Enhanced Utilities
- `simple_visualize_tiffs.py` - Multi-state visualization support
- `examples/demo_auto_downloader.ipynb` - Interactive Jupyter notebook demonstrations

### Testing Infrastructure
- `download_city_new.py` - Updated city download script for testing
- Test area data for validation scenarios

## 🔧 Technical Implementation

### State Detection Algorithm
```python
def detect_states(self, area_polygon):
    """Detects which German federal states intersect with the given area"""
    # Uses shapely geometric operations to find intersecting states
    # Returns list of state names for WMS service selection
```

### Multi-Service Download Coordination
```python
def download_all_states(self, area_name, area_polygon, out_path, grid_spacing, image_type):
    """Coordinates downloads across multiple WMS services"""
    # Automatically instantiates correct WMS downloaders
    # Handles state-specific area clipping
    # Manages parallel downloads and error handling
```

### File Organization
```
output_directory/
├── Baden-Württemberg/
│   ├── 1.tiff
│   ├── 2.tiff
│   └── ...
├── Bayern/
│   ├── 1.tiff
│   ├── 2.tiff
│   └── ...
└── metadata.json
```

## 🎯 Use Cases Addressed

1. **Urban Planning**: Cross-border metropolitan areas (e.g., Ulm/Neu-Ulm)
2. **Research Projects**: Large-scale studies spanning multiple states
3. **Infrastructure Planning**: Transportation corridors crossing state boundaries
4. **Environmental Monitoring**: River basins and natural areas extending across states

## 🔍 Testing Commands

To reproduce the testing and validation:

```bash
# Download and visualize Mainz (single state)
python auto_downloader_docs.py  # Run Mainz example

# Download München (single state, specific coordinates)
python download_city_new.py    # Run München example

# Download Ulm/Neu-Ulm (cross-border)
python auto_downloader_docs.py  # Run Ulm example

# Visualize all downloaded orthophotos
python simple_visualize_tiffs.py
```

## 🚦 Breaking Changes
None - This is a purely additive implementation that maintains full backward compatibility with existing WMS downloader classes.

## 📋 Checklist
- [x] Multi-state detection algorithm implemented
- [x] Cross-border download functionality working
- [x] Comprehensive test coverage (Mainz, München, Ulm/Neu-Ulm)
- [x] Documentation and examples provided
- [x] Visualization pipeline updated
- [x] Backward compatibility maintained
- [x] Code follows project style guidelines
- [x] All tests passing

## 🎉 Ready for Review
This implementation successfully addresses the multi-state orthophoto download requirements and has been thoroughly tested with real-world scenarios. The code is ready for integration into the main project.
