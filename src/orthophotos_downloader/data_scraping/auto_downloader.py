"""
Automatic WMS downloader that detects which services are needed for a given area
and orchestrates downloads across multiple WMS services.
"""

import geopandas as gpd
import importlib
import logging
from typing import List, Dict, Optional, Union, Tuple
from pathlib import Path
from shapely.geometry import Polygon
from geopandas import GeoDataFrame, GeoSeries

from orthophotos_downloader.data_scraping.image_download import ImageDownloader, AreaDataset

logger = logging.getLogger(__name__)


class AutoOrthophotoDownloader:
    """
    Automatically detects which WMS services are needed for a given area
    and downloads orthophotos from all relevant services.
    """
    
    # Mapping of German federal state codes to their corresponding WMS downloader classes
    STATE_TO_RGB_DOWNLOADER = {
        'BW': 'BW_RGB_Dop20_ImageDownloader',
        'BY': 'BY_RGB_Dop20_ImageDownloader', 
        'BE': 'BE_RGB_Dop20_ImageDownloader',
        'BB': 'BB_RGB_Dop20_ImageDownloader',
        'HB': 'HB_RGB_Dop20_ImageDownloader',
        'HH': 'HH_RGB_Dop20_ImageDownloader',
        'HE': 'HE_RGB_Dop20_ImageDownloader',
        'MV': 'MV_RGB_Dop20_ImageDownloader',
        'NI': 'NI_RGB_Dop20_ImageDownloader',
        'NW': 'NW_RGB_Dop20_ImageDownloader',
        'RP': 'RP_RGB_Dop20_ImageDownloader',
        'SL': 'SL_RGB_Dop20_ImageDownloader',
        'SN': 'SN_RGB_Dop20_ImageDownloader',
        'ST': 'ST_RGB_Dop20_ImageDownloader',
        'SH': 'SH_RGB_Dop20_ImageDownloader',
        'TH': 'TH_RGB_Dop20_ImageDownloader',
    }
    
    STATE_TO_CIR_DOWNLOADER = {
        'BW': 'BW_CIR_Dop20_ImageDownloader',
        'BY': 'BY_CIR_Dop20_ImageDownloader',
        'BE': 'BE_CIR_Dop20_ImageDownloader',
        'BB': 'BB_CIR_Dop20_ImageDownloader',
        'HB': 'HB_CIR_Dop20_ImageDownloader',
        'HH': 'HH_CIR_Dop20_ImageDownloader',
        'HE': 'HE_CIR_Dop20_ImageDownloader',
        'MV': 'MV_CIR_Dop20_ImageDownloader',
        'NI': 'NI_CIR_Dop20_ImageDownloader',
        'NW': 'NW_CIR_Dop20_ImageDownloader',
        'RP': 'RP_CIR_Dop20_ImageDownloader',
        'SL': 'SL_CIR_Dop20_ImageDownloader',
        'SN': 'SN_CIR_Dop20_ImageDownloader',
        'ST': 'ST_CIR_Dop20_ImageDownloader',
        'SH': 'SH_CIR_Dop20_ImageDownloader',
        'TH': 'TH_CIR_Dop20_ImageDownloader',
    }
    
    def __init__(self, grid_spacing: int, german_states_url: Optional[str] = None):
        """
        Initialize the AutoOrthophotoDownloader.
        
        Args:
            grid_spacing: The grid spacing in meters for the image download.
            german_states_url: URL to German federal states GeoJSON. If None, uses default.
        """
        self.grid_spacing = grid_spacing
        self.german_states_url = german_states_url or "https://raw.githubusercontent.com/isellsoap/deutschlandGeoJSON/main/2_bundeslaender/4_niedrig.geo.json"
        self._states_gdf = None
        
    def _load_german_states(self) -> GeoDataFrame:
        """Load German federal states geometry data."""
        if self._states_gdf is None:
            logger.info(f"Loading German federal states from {self.german_states_url}")
            self._states_gdf = gpd.read_file(self.german_states_url).to_crs("EPSG:25832")
        return self._states_gdf
    
    def detect_intersecting_states(self, area_polygon: Union[GeoSeries, GeoDataFrame, Polygon]) -> List[Tuple[str, str, Polygon]]:
        """
        Detect which German federal states intersect with the given area.
        
        Args:
            area_polygon: The area of interest as GeoSeries, GeoDataFrame, or Shapely Polygon.
            
        Returns:
            List of tuples containing (state_name, state_code, intersection_geometry)
        """
        # Convert input to GeoDataFrame if needed
        if isinstance(area_polygon, Polygon):
            area_gdf = gpd.GeoDataFrame([1], geometry=[area_polygon], crs="EPSG:25832")
        elif isinstance(area_polygon, GeoSeries):
            area_gdf = gpd.GeoDataFrame([1], geometry=[area_polygon.unary_union], crs=area_polygon.crs)
        elif isinstance(area_polygon, GeoDataFrame):
            area_gdf = area_polygon.copy()
        else:
            raise ValueError("area_polygon must be a Polygon, GeoSeries, or GeoDataFrame")
            
        # Ensure CRS compatibility
        if area_gdf.crs != "EPSG:25832":
            area_gdf = area_gdf.to_crs("EPSG:25832")
            
        # Load German states
        states_gdf = self._load_german_states()
        
        # Find intersecting states
        intersecting_states = []
        area_geom = area_gdf.unary_union
        
        for _, state_row in states_gdf.iterrows():
            state_geom = state_row.geometry
            if area_geom.intersects(state_geom):
                intersection = area_geom.intersection(state_geom)
                if not intersection.is_empty:
                    state_name = state_row["name"]
                    state_code = state_row["id"].split("-")[-1]  # Extract code like "BY" from "DE-BY"
                    intersecting_states.append((state_name, state_code, intersection))
                    
        logger.info(f"Found {len(intersecting_states)} intersecting states: {[s[0] for s in intersecting_states]}")
        return intersecting_states
    
    def _get_downloader_class(self, state_code: str, image_type: str = "RGB"):
        """
        Get the appropriate downloader class for a state and image type.
        
        Args:
            state_code: The federal state code (e.g., "BY", "BW")
            image_type: "RGB" or "CIR"
            
        Returns:
            The downloader class
        """
        if image_type == "RGB":
            downloader_mapping = self.STATE_TO_RGB_DOWNLOADER
        elif image_type == "CIR":
            downloader_mapping = self.STATE_TO_CIR_DOWNLOADER
        else:
            raise ValueError("image_type must be 'RGB' or 'CIR'")
            
        if state_code not in downloader_mapping:
            raise ValueError(f"No {image_type} downloader available for state: {state_code}")
            
        downloader_class_name = downloader_mapping[state_code]
        
        # Dynamically import the downloader class
        try:
            mod = importlib.import_module("orthophotos_downloader.data_scraping.wms_germany")
            downloader_class = getattr(mod, downloader_class_name)
            return downloader_class
        except (ImportError, AttributeError) as e:
            raise ImportError(f"Could not import {downloader_class_name}: {e}")
    
    def download_images_auto(
        self,
        area_name: str,
        area_polygon: Union[GeoSeries, GeoDataFrame, Polygon],
        out_path: Path,
        image_type: str = "RGB",
        filename_prefix: Optional[str] = None,
        mask: Optional[Union[GeoSeries, GeoDataFrame]] = None,
        buffer_size: int = 0
    ) -> Dict[str, AreaDataset]:
        """
        Automatically download orthophotos for an area that may span multiple federal states.
        
        Args:
            area_name: Name of the area for identification
            area_polygon: The area of interest
            out_path: Output path where images will be saved
            image_type: "RGB" or "CIR"
            filename_prefix: Optional prefix for filenames
            mask: Optional mask to limit downloads to specific areas
            buffer_size: Buffer size around the area
            
        Returns:
            Dictionary mapping state names to their AreaDataset results
        """
        # Detect intersecting states
        intersecting_states = self.detect_intersecting_states(area_polygon)
        
        if not intersecting_states:
            raise ValueError("No German federal states intersect with the given area")
            
        results = {}
        
        for state_name, state_code, intersection_geom in intersecting_states:
            logger.info(f"Processing {state_name} ({state_code})...")
            
            try:
                # Get the appropriate downloader class
                downloader_class = self._get_downloader_class(state_code, image_type)
                
                # Instantiate the downloader
                downloader = downloader_class(grid_spacing=self.grid_spacing)
                
                # Create GeoSeries for the intersection
                intersection_gs = gpd.GeoSeries([intersection_geom], crs="EPSG:25832")
                
                # Create state-specific output directory
                state_out_path = out_path / f"{state_name.replace('/', '_')}"
                state_out_path.mkdir(parents=True, exist_ok=True)
                
                # Download images for this state's portion
                state_prefix = f"{filename_prefix}_{state_code}" if filename_prefix else state_code
                
                result = downloader.download_images_from_polygon(
                    area_name=f"{area_name}_{state_name}",
                    area_polygon=intersection_gs,
                    out_path=state_out_path,
                    mask=mask,
                    buffer_size=buffer_size
                )
                
                results[state_name] = result
                logger.info(f"✅ {state_name}: {len(result.images)} images downloaded")
                
            except Exception as e:
                logger.error(f"❌ Failed to download from {state_name} ({state_code}): {e}")
                continue
                
        return results
    
    def download_rgb_images_auto(
        self,
        area_name: str,
        area_polygon: Union[GeoSeries, GeoDataFrame, Polygon],
        out_path: Path,
        filename_prefix: Optional[str] = None,
        mask: Optional[Union[GeoSeries, GeoDataFrame]] = None,
        buffer_size: int = 0
    ) -> Dict[str, AreaDataset]:
        """
        Automatically download RGB orthophotos for an area that may span multiple federal states.
        """
        return self.download_images_auto(
            area_name=area_name,
            area_polygon=area_polygon,
            out_path=out_path,
            image_type="RGB",
            filename_prefix=filename_prefix,
            mask=mask,
            buffer_size=buffer_size
        )
    
    def download_cir_images_auto(
        self,
        area_name: str,
        area_polygon: Union[GeoSeries, GeoDataFrame, Polygon],
        out_path: Path,
        filename_prefix: Optional[str] = None,
        mask: Optional[Union[GeoSeries, GeoDataFrame]] = None,
        buffer_size: int = 0
    ) -> Dict[str, AreaDataset]:
        """
        Automatically download CIR orthophotos for an area that may span multiple federal states.
        """
        return self.download_images_auto(
            area_name=area_name,
            area_polygon=area_polygon,
            out_path=out_path,
            image_type="CIR",
            filename_prefix=filename_prefix,
            mask=mask,
            buffer_size=buffer_size
        )
    
    def download_rgbi_images_auto(
        self,
        area_name: str,
        area_polygon: Union[GeoSeries, GeoDataFrame, Polygon],
        out_path: Path,
        mask: Optional[Union[GeoSeries, GeoDataFrame]] = None,
        buffer_size: int = 0
    ) -> Dict[str, AreaDataset]:
        """
        Automatically download and merge RGBI orthophotos for an area that may span multiple federal states.
        
        This function will download both RGB and CIR images for each intersecting state,
        then merge them into RGBI images using the RGBIImageDownloader.
        """
        # Import here to avoid circular imports
        from orthophotos_downloader.data_scraping.image_download import RGBIImageDownloader
        
        # Detect intersecting states
        intersecting_states = self.detect_intersecting_states(area_polygon)
        
        if not intersecting_states:
            raise ValueError("No German federal states intersect with the given area")
            
        results = {}
        
        for state_name, state_code, intersection_geom in intersecting_states:
            logger.info(f"Processing RGBI for {state_name} ({state_code})...")
            
            try:
                # Get RGB and CIR downloader classes
                rgb_downloader_class = self._get_downloader_class(state_code, "RGB")
                cir_downloader_class = self._get_downloader_class(state_code, "CIR")
                
                # Instantiate the downloaders
                rgb_downloader = rgb_downloader_class(grid_spacing=self.grid_spacing)
                cir_downloader = cir_downloader_class(grid_spacing=self.grid_spacing)
                
                # Create RGBI downloader
                rgbi_downloader = RGBIImageDownloader(rgb_downloader, cir_downloader)
                
                # Create GeoSeries for the intersection
                intersection_gs = gpd.GeoSeries([intersection_geom], crs="EPSG:25832")
                
                # Create state-specific output directory
                state_out_path = out_path / f"{state_name.replace('/', '_')}"
                state_out_path.mkdir(parents=True, exist_ok=True)
                
                # Download RGBI images for this state's portion
                result = rgbi_downloader.download_rgbi_images_from_polygon(
                    area_name=f"{area_name}_{state_name}",
                    area_polygon=intersection_gs,
                    out_path=state_out_path,
                    mask=mask,
                    buffer_size=buffer_size
                )
                
                results[state_name] = result
                logger.info(f"✅ {state_name}: {len(result.images)} RGBI images downloaded")
                
            except Exception as e:
                logger.error(f"❌ Failed to download RGBI from {state_name} ({state_code}): {e}")
                continue
                
        return results


def auto_download_orthophotos(
    area_name: str,
    area_polygon: Union[GeoSeries, GeoDataFrame, Polygon],
    out_path: Path,
    grid_spacing: int = 1000,
    image_type: str = "RGB",
    filename_prefix: Optional[str] = None,
    mask: Optional[Union[GeoSeries, GeoDataFrame]] = None,
    buffer_size: int = 0
) -> Dict[str, AreaDataset]:
    """
    Convenience function to automatically download orthophotos.
    
    This function automatically detects which WMS services are needed for the given area
    and downloads orthophotos from all relevant services.
    
    Args:
        area_name: Name of the area for identification
        area_polygon: The area of interest (GeoSeries, GeoDataFrame, or Shapely Polygon)
        out_path: Output path where images will be saved
        grid_spacing: The grid spacing in meters for the image download (default: 1000)
        image_type: "RGB", "CIR", or "RGBI" (default: "RGB")
        filename_prefix: Optional prefix for filenames
        mask: Optional mask to limit downloads to specific areas
        buffer_size: Buffer size around the area (default: 0)
        
    Returns:
        Dictionary mapping state names to their AreaDataset results
        
    Example:
        >>> import geopandas as gpd
        >>> from pathlib import Path
        >>> from orthophotos_downloader.data_scraping.auto_downloader import auto_download_orthophotos
        >>> 
        >>> # Load your area of interest
        >>> area = gpd.read_file('my_area.geojson')
        >>> 
        >>> # Automatically download RGB orthophotos
        >>> results = auto_download_orthophotos(
        ...     area_name="my_area",
        ...     area_polygon=area.geometry,
        ...     out_path=Path("./downloads"),
        ...     grid_spacing=1000,
        ...     image_type="RGB"
        ... )
    """
    auto_downloader = AutoOrthophotoDownloader(grid_spacing=grid_spacing)
    
    if image_type == "RGB":
        return auto_downloader.download_rgb_images_auto(
            area_name=area_name,
            area_polygon=area_polygon,
            out_path=out_path,
            filename_prefix=filename_prefix,
            mask=mask,
            buffer_size=buffer_size
        )
    elif image_type == "CIR":
        return auto_downloader.download_cir_images_auto(
            area_name=area_name,
            area_polygon=area_polygon,
            out_path=out_path,
            filename_prefix=filename_prefix,
            mask=mask,
            buffer_size=buffer_size
        )
    elif image_type == "RGBI":
        return auto_downloader.download_rgbi_images_auto(
            area_name=area_name,
            area_polygon=area_polygon,
            out_path=out_path,
            mask=mask,
            buffer_size=buffer_size
        )
    else:
        raise ValueError("image_type must be 'RGB', 'CIR', or 'RGBI'")
