import imageio.v3 as io
import logging
import numpy as np
import rasterio
import json
from numbers import Number
from concurrent.futures import ThreadPoolExecutor

from dataclasses import dataclass
from decimal import Decimal
from geopandas import GeoDataFrame, GeoSeries
from owslib.map.wms111 import WebMapService_1_1_1
from owslib.map.wms130 import WebMapService_1_3_0
from owslib.wms import WebMapService
from owslib.util import ResponseWrapper
from pathlib import Path
from rasterio.features import rasterize
from rasterio.transform import from_origin
from shapely.geometry import Polygon, mapping, shape
from time import perf_counter
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Image:
    """
    Represents an image downloaded from a source.

    Attributes:
        image_path: The path to the downloaded image file.
        mask_path: The path to the generated mask file (if mask was provided).
        upper_left_x: The x-coordinate of the upper-left corner of the image.
        upper_left_y: The y-coordinate of the upper-left corner of the image.
        download_time: The time it took to download the image in seconds.
        width_m: The width of the image in meters.
        height_m: The height of the image in meters.
        width_px: The width of the image in pixels.
        height_px: The height of the image in pixels.
        resolution_m: Pixel resolution in meters.
        crs: Coordinate Reference System in EPSG format (e.g. 'EPSG:25832').
    """

    image_path: Path
    mask_path: Optional[Path]
    upper_left_x: float
    upper_left_y: float
    download_time: float
    width_m: int
    height_m: int
    width_px: int
    height_px: int
    resolution_m: float
    crs: str

    def __post_init__(self):
        """Perform post-initialization tasks which ensure the correct data types."""
        if not isinstance(self.image_path, Path) and self.image_path is not None:
            object.__setattr__(self, "image_path", Path(self.image_path))
        if not isinstance(self.mask_path, Path) and self.mask_path is not None:
            object.__setattr__(self, "mask_path", Path(self.mask_path))

    def to_dict(self) -> dict:
        """Return a serializable dictionary representation of the Image object."""
        return {k: v if isinstance(v, Number) else str(v) for k, v in self.__dict__.items()}


@dataclass
class AreaDataset:
    """
    Represents a dataset for a specific area.

    Attributes:
        name: The name of the dataset.
        polygon: The polygon representing the area of interest.
        buffer_size: The buffer size around the area of interest.
        out_path: The output path where the downloaded images will be saved.
        images: The list of images in the dataset (optional).
    """

    name: str
    polygon: str
    buffer_size: int
    out_path: Path
    images: Optional[List[Image]] = None

    def to_dict(self, save_polygon_to: Path) -> dict:
        """
        Converts the AreaDataset to dictionary.
        In the background it saves the polygon as a geojson file and stores only the path in the result.
        """

        if self.images is None:
            logger.exception(msg="Cannot convert AreaDataset to dict without images.")
            raise ValueError("Cannot convert AreaDataset to dict without images.")

        if save_polygon_to.is_dir():
            # TODO: convert to EPSG 4326 (lat/lon) before saving because this is the standard for geojson
            save_polygon_to = save_polygon_to / "polygon.geojson"

        # dump polygon as geojson to disk
        with open(save_polygon_to, "w") as f:
            json.dump(self.polygon.__geo_interface__, f, indent=4)
        logger.info(f"Saved Polygon for {self.name} to {save_polygon_to}")

        return {
            "name": self.name,
            "polygon": str(save_polygon_to),
            "buffer_size": self.buffer_size,
            "out_path": str(self.out_path),
            "images": [i.to_dict() for i in self.images],
        }

    def __post_init__(self):
        """Perform post-initialization tasks which ensure the correct data types."""

        # cast out_path to Path and create the directory if it does not exist
        if not isinstance(self.out_path, Path):
            self.out_path = Path(self.out_path)
        self.out_path.mkdir(parents=True, exist_ok=True)

        # if necessary, convert dict-dump of Image instances back to Image
        if self.images is not None:
            self.images = [Image(**i) if isinstance(i, dict) else i for i in self.images]

        # try to read the polygon from disk if it is not a Polygon object already
        if not isinstance(self.polygon, Polygon):
            if isinstance(self.polygon, str):
                self.polygon = Path(self.polygon)
            try:
                with open(self.polygon, "r") as f:
                    polygon_shape = shape(json.load(f))
                self.polygon = polygon_shape
            except FileNotFoundError as f:
                logger.error(f"Could not read polygon from disk at {self.polygon}")
                raise f


class ExtendedWebMapService:
    """
    A class representing an extended Web Map Service (WMS) for image downloading.

    Args:
        url: The URL of the WMS server.
        version: The version of the WMS protocol.
        resolution: The resolution in meters per pixel.
        layer_name: The name of the layer to download.
        crs: The coordinate reference system in EPSG format (e.g. 'EPSG:25832').
        format: The image format to download.

    Attributes:
        wms: The WebMapService instance.
        resolution: The resolution in meters per pixel.
        layer_name: The name of the layer to download.
        crs: The coordinate reference system in EPSG format (e.g. 'EPSG:25832').
        format: The image format to download.
    """

    def __init__(
        self, url: str, version: str, resolution: float, layer_name: str, crs: str, format: str
    ):
        """
        Initialize the ExtendedWebMapService object.

        Args:
            url: The URL of the Web Map Service (WMS).
            version: The version of the WMS.
            resolution: The resolution in meters per pixel.
            layer_name: The name of the layer to download.
            crs: The coordinate reference system in EPSG format (e.g. 'EPSG:25832').
            format: The image format to download.
        """
        self.wms: WebMapService_1_1_1 | WebMapService_1_3_0 = WebMapService(
            url=url, version=version
        )
        self.resolution: float = resolution  # meters per pixel
        self.layer_name: str = layer_name
        self.crs: str = crs  # EPSG format
        self.format: str = format
        self.bounding_box = None  # Initialize bounding_box attribute

    def getmap(self, bbox, size) -> ResponseWrapper:
        """
        Override the getmap() function of the WebMapService class.

        Args:
            bbox: The bounding box coordinates of the image.
            size: The size of the image.

        Returns:
            ResponseWrapper: The downloaded image.
        """
        return self.wms.getmap(
            layers=[self.layer_name], srs=self.crs, bbox=bbox, size=size, format=self.format
        )

    def to_dict(self) -> dict:
        """Return a serializable dictionary representation of the object."""
        r = {k: v if isinstance(v, Number) else str(v) for k, v in self.__dict__.items()}
        r["url"], r["version"] = self.wms.url, self.wms.version
        del r["wms"]
        return r


class ImageDownloader:
    """
    A class for downloading images using a grid-based approach.

    This class is responsible for downloading images for a specified area using a grid.
    It utilizes a provided Web Map Service (WMS) to request images for each tile in the grid.
    The downloaded images are saved as GeoTIFF files.

    Attributes:
        wms: The Web Map Service used to request images.
        grid_spacing: The spacing between grid points (i.e. height and width of grid tiles) in meters.
        width_m: The width of each grid tile in meters.
        height_m: The height of each grid tile in meters.
        width_px: The width of each grid tile in pixels.
        height_px: The height of each grid tile in pixels.
    """

    def __init__(self, wms: ExtendedWebMapService, grid_spacing: int):
        """
        Initialize the ImageDownloader object.

        Args:
            wms: The WebMapService object used for downloading images.
            grid_spacing: The spacing between grid points (i.e. height and width of grid tiles) in meters.

        Raises:
            ValueError: If `grid_spacing` is not a multiple of the resolution of the provided WMS.
        """
        self.wms = wms
        self.grid_spacing = grid_spacing
        self.width_m = grid_spacing
        self.height_m = grid_spacing
        # the width and height in pixels are defined by the resolution of the dataset
        self.width_px: int = int(self.grid_spacing / self.wms.resolution)
        self.height_px: int = int(self.grid_spacing / self.wms.resolution)

        # check if grid_spacing / wms.resolution is an integer
        if Decimal(str(grid_spacing)) % Decimal(str(wms.resolution)) != 0:
            raise ValueError(
                "'grid_spacing' must be a multiple of the resolution of the provided WMS."
            )

    def _validate_geoseries(self, geoseries: GeoSeries, argname: str) -> bool:
        """
        Validates the requirements of a GeoSeries object for usage in 'download_images_from_polygon()'.

        Args:
            geoseries: The GeoSeries object to validate.
            argname: The name of the argument being validated.

        Returns:
            bool: True if the GeoSeries is valid.

        Raises:
            ValueError: If the GeoSeries is not valid.
        """

        # make sure it is is a GeoSeries
        if not isinstance(geoseries, GeoSeries):
            logger.error(f"Expected GeoSeries for argument '{argname}', but got {type(geoseries)}.")
            raise ValueError(f"Expected GeoSeries for '{argname}'.")

        # make sure the GeoSeries only contains one polygon
        if len(geoseries) != 1:
            logger.error(
                f"Expected GeoSeries of length 1 for argument '{argname}', but got GeoSeries of length {geoseries.length}."
            )
            raise ValueError(f"Expected GeoSeries of length 1 for argument '{argname}'.")

        # make sure the CRS of the GeoSeries matches the CRS of the WMS
        if not ":".join(geoseries.geometry.crs.to_authority()) == self.wms.crs:
            logger.error(
                f"CRS of '{argname}' ({geoseries.crs}) does not match the CRS of the WMS ({self.wms.crs})."
            )
            raise ValueError(f"CRS of '{argname}' does not match the CRS of the WMS.")

        return True

    def _prepare_image_download(
        self,
        area_polygon: GeoSeries,
        out_path: Path | str,
        buffer_size: int,
        mask: Optional[GeoSeries],
    ) -> GeoDataFrame:
        """
        This method prepares the image download by creating a grid of tiles covering the polygon
        defined in the ImageDownloader instance. Therefore, it buffers the provided polygon to ensure
        full coverage. It then creates a grid of tiles (using the grid_spacing specified during initialization)

        After creating the grid, it filters out any grid tiles that do not intersect with the mask (if provided).

        Args:
            area_polygon: The polygon for which images will be downloaded. Must be provided as a GeoSeries of length one to ensure CRS information is included.
            out_path: The output path where the downloaded images will be saved.
            buffer_size: The buffer size applied to the polygon to ensure full coverage.
            mask: Only images intersecting with this mask will be downloaded. Must be provided as a GeoSeries of length one to ensure CRS information is included.

        Returns:
            A GeoDataFrame containing the grid of squares.
        """
        # validate the input GeoSeries 'area_polygon' and 'mask'
        self._validate_geoseries(area_polygon, "area_polygon")
        if mask is not None:
            self._validate_geoseries(mask, "mask")

        # extract only the polygon from the passed GeoSeries for the next steps
        area_polygon = area_polygon.iloc[0]

        # calculate the grid of tiles that will be used to request the images
        grid = self._make_grid(area_polygon, buffer_size, self.grid_spacing)

        # filter any grid tiles not intersecting with the mask
        if mask is not None:
            len_before = len(grid)
            grid = grid.loc[grid.intersects(mask.iloc[0])]
            logger.info(f"Total images: {len_before}")
            logger.info(f"Filtered images (using the provided mask): {len_before - len(grid)}")
            logger.info(f"Images to process: {len(grid)}")

        # create the output directory for the images
        if not isinstance(out_path, Path):
            out_path = Path(out_path)

        return grid

    def download_images_from_polygon(
        self,
        area_name: str,
        area_polygon: GeoSeries,
        out_path: Path | str,
        buffer_size: int = 0,
        mask: Optional[GeoSeries] = None,
        driver: str = "GTiff",
        file_extension: str = "tiff",
    ) -> Optional[AreaDataset]:
        """
        Downloads images for the specified polygon using the provided grid.

        The method first gathers a list of tiles to be downloaded and then
        iterates over the tiles to download the corresponding images.

        Args:
            area_name: The name of the area dataset.
            area_polygon: The polygon for which images will be downloaded. Must be provided as a GeoSeries of length one to ensure CRS information is included.
            out_path: The output path where the downloaded images will be saved.
            buffer_size: The buffer size applied to the polygon to ensure full coverage.
            mask: Only images intersecting with this mask will be downloaded. Must be provided as a GeoSeries of length one to ensure CRS information is included.
            driver: The rasterio driver to use for saving the image (should fit the file extension parameter).
            file_extension: The file extension to use for the downloaded images.

        Returns:
            An AreaDataset object containing (among others) a list of downloaded images. When single image downloads fail, the method still finishes, but failed
            images are not stored to disk and they are included in the AreaDataset as Image instances with empty paths.
        """

        # Ensure out_path is a Path object
        if not isinstance(out_path, Path):
            out_path = Path(out_path)
        # get the grid of tiles that have to be downloaded
        grid = self._prepare_image_download(area_polygon, out_path, buffer_size, mask)

        # extract only the polygon from the passed GeoSeries for the next steps
        area_polygon = area_polygon.iloc[0]

        # create the instance of AreaDataset holding the images
        result_obj = AreaDataset(area_name, area_polygon, buffer_size, out_path)
        images = []

        logger.info(f"Downloading {len(grid)} images for {area_name}...")

        for i, tile in enumerate(grid.itertuples()):
            logger.info(f"Start downloading image {i + 1} of {len(grid)}...")
            start_time = perf_counter()
            try:
                images.append(
                    ImageDownloader.download_single_image(
                        img_path=out_path / f"{i + 1}.{file_extension}",
                        bounding_box=tile.geometry,
                        wms=self.wms,
                        width_px=self.width_px,
                        height_px=self.height_px,
                        mask=mask,
                        driver=driver,
                    )
                )
                logger.info(
                    f"Finished downloading image {i+1} in {perf_counter() - start_time:.2f} seconds.\n"
                )

            # when the image download fails, create an empty image instance to prevent the loop from breaking
            # because of a single failed image download
            except Exception as e:
                logger.error(f"Error downloading image {i+1}. Append empty image to images list...")
                logger.exception(e)
                images.append(
                    Image(
                        image_path=None,
                        mask_path=None,
                        upper_left_x=tile.geometry.bounds[0],
                        upper_left_y=tile.geometry.bounds[3],
                        download_time=perf_counter() - start_time,
                        width_m=self.grid_spacing,
                        height_m=self.grid_spacing,
                        width_px=self.width_px,
                        height_px=self.height_px,
                        resolution_m=self.wms.resolution,
                        crs=self.wms.crs,
                    )
                )

        result_obj.images = images
        return result_obj

    @staticmethod
    def download_single_image(
        img_path: Path,
        bounding_box: Polygon,
        wms: ExtendedWebMapService,
        width_px: int,
        height_px: int,
        mask: Optional[GeoSeries] = None,
        driver: str = "GTiff",
    ) -> Image:
        """
        Downloads a single image from a Web Map Service (WMS) for a given tile and saves it as a GeoTIFF file.
        Optionally, a binary mask image can also be saved if a mask is provided.

        Args:
            img_path: The output path where the downloaded image will be saved. Must include the filename and suffix (e.g. /path/to/file/img.tiff).
            bounding_box: The outer border of the image to be downloaded.
            wms: The Web Map Service object used to request the image.
            width_px: The width of the image in pixels.
            height_px: The height of the image in pixels.
            mask: Only images intersecting with this mask will be downloaded. Must be provided as a GeoSeries of length one to ensure CRS information is included.
            driver: The rasterio driver to use for saving the image (should fit the file format used in the out_path parameter).
        Returns:
            Image: An instance of the Image class containing metadata about the downloaded image.
        """

        # TODO: validate width / height and resolution of WMS + bounding box of image

        # TODO: check if the requested image type (png, jpg, tiff), the rasterio driver / file format is valid
        # affect each other in any way and if we need to implement a check of some sort (for now we only request tif, hard-code *.tiff and "GTiff")

        start_time = perf_counter()

        # request the image for the current tile from the WMS using the tile as a bounding box
        response = wms.getmap(
            bbox=bounding_box.bounds,
            size=(width_px, height_px),  # these are pixels
        )

        # read image data and image metadata
        result = response.read()
        img = io.imread(result, index=None)[:, :, :3]  # remove alpha channel

        # derive the mask path from the img_path
        mask_path = img_path.with_stem(f"{img_path.stem}_mask") if mask is not None else None

        # extract the coordinates of the upper left corner of the bounding box
        upper_left_x = bounding_box.bounds[0]
        upper_left_y = bounding_box.bounds[3]

        # define the configuration for the export as GeoTIFF
        metadata = {
            "driver": driver,
            "dtype": rasterio.uint8,
            "nodata": None,
            "width": width_px,  # The number of pixels in x-direction
            "height": height_px,  # The number of pixels in y-direction
            "count": 3,  # The number of bands in your image
            "crs": rasterio.crs.CRS.from_string(wms.crs),  # The coordinate reference system
            "transform": from_origin(
                upper_left_x,
                upper_left_y,
                wms.resolution,
                wms.resolution,
            ),
        }

        # export image as GeoTiff
        with rasterio.open(img_path, "w", **metadata) as dst:
            dst.write(img.transpose((2, 0, 1)))
            logger.info(f"Image saved to {img_path}")

        # export binary mask image if mask is provided
        if mask is not None:
            # create binary mask image
            mask_img = rasterize(
                [(mapping(mask.iloc[0].intersection(bounding_box)), 1)],
                out_shape=(height_px, width_px),
                transform=from_origin(upper_left_x, upper_left_y, wms.resolution, wms.resolution),
                fill=0,
                dtype=rasterio.uint8,
            )

            # configure metadata to write binary mask image
            metadata.update({"count": 1})

            # write binary mask iamge to file
            with rasterio.open(mask_path, "w", nbits=1, **metadata) as dst:
                dst.write(mask_img, 1)
                logger.info(f"Mask saved to {mask_path}")

        # append the Image instance to the ImageDownloader's images
        return Image(
            image_path=img_path,
            mask_path=mask_path,
            upper_left_x=upper_left_x,
            upper_left_y=upper_left_y,
            width_m=width_px * wms.resolution,
            height_m=height_px * wms.resolution,
            width_px=width_px,
            height_px=height_px,
            resolution_m=wms.resolution,
            crs=wms.crs,
            download_time=perf_counter() - start_time,
        )

    @staticmethod
    def delete_images(dir_path: Path | str) -> bool:
        """
        Deletes all files in the output path of the area dataset.

        Args:
            dir_path: The directory to be deleted (including its contents).

        Returns:
            True if all files and the directory were successfully deleted, False otherwise.
        """

        if not isinstance(dir_path, Path):
            dir_path = Path(dir_path)

        # check if dir_path exists
        if not dir_path.exists():
            logger.error(f"Path '{dir_path}' passed to delete_images() does not exist.")
            return False

        # check if dir_path is emtpy
        if not list(dir_path.iterdir()):
            logger.warning(f"Path '{dir_path}' passed to delete_images() is already empty.")

        # check if dir_path contains files other than images
        if any([f.suffix not in [".png", ".tiff"] for f in dir_path.iterdir()]):
            logger.error(f"Path '{dir_path}' passed to delete_images() contains not only images.")
            return False

        try:
            cnt = 0
            for file in dir_path.iterdir():
                file.unlink()
                cnt += 1
            dir_path.rmdir()
            logger.info(f"Deleted {cnt} images from '{dir_path}'.")
            return True

        except Exception as e:
            logger.error(f"Error deleting directory '{dir_path}' and its contents: {e}")
            return False

    @staticmethod
    def _make_grid(
        area_polygon: Polygon, buffer_size: int, grid_spacing: int
    ) -> GeoDataFrame:  # TODO this function does not generates well to any other coordinate system
        """
        Creates a grid of squares that fully covers the specified area of interest.

        Args:
            area_polygon: The area of interest.
            buffer_size: The buffer size to apply to the area of interest.
            grid_spacing: The spacing between grid squares.

        Returns:
            A GeoDataFrame containing the grid of squares.
        """

        # apply a buffer of on grid_spacing to ensure coverage of edges
        buffered_area = area_polygon.buffer(buffer_size)

        # Get the bounds of the polygon
        minx, miny, maxx, maxy = buffered_area.bounds

        # Create a grid of points within these bounds
        x_coords = list(np.arange(np.floor(minx), np.ceil(maxx), grid_spacing))
        y_coords = list(np.arange(np.floor(miny), np.ceil(maxy), grid_spacing))

        # round to even thousands to match the grid
        x_coords = [round(x, -3) for x in x_coords]
        y_coords = [round(y, -3) for y in y_coords]

        # ensure to cover the whole area by expanding the grid by one grid_spacing in each direction
        x_coords = [x_coords[0] - grid_spacing] + x_coords + [x_coords[-1] + grid_spacing]
        y_coords = [y_coords[0] - grid_spacing] + y_coords + [y_coords[-1] + grid_spacing]

        # Create squares around each point
        grid = []
        for x in x_coords:
            for y in y_coords:
                # Create a square (as a polygon) around the point
                square = Polygon(
                    [
                        (x, y),
                        (x + grid_spacing, y),
                        (x + grid_spacing, y + grid_spacing),
                        (x, y + grid_spacing),
                    ]
                )

                if buffered_area.intersects(square):
                    grid.append(square)

        # Convert the list of squares to a GeoDataFrame
        return GeoDataFrame(geometry=grid)

    def to_dict(self) -> dict:
        """Return a serializable dictionary representation of the ImageDownloader object."""
        r = {k: v if isinstance(v, Number) else str(v) for k, v in self.__dict__.items()}
        r["wms"] = self.wms.to_dict()
        return r


class CentralWMSManager:
    """
    A central class to manage WMS services and handle AOI-based downloads.
    """

    def __init__(self, wms_metadata: List[dict]):
        """
        Initialize the CentralWMSManager with metadata for available WMS services.

        Args:
            wms_metadata: A list of dictionaries containing metadata for WMS services.
                          Each dictionary should include keys like 'url', 'version',
                          'resolution', 'layer_name', 'crs', 'format', and 'bounding_box'.
        """
        self.wms_metadata = wms_metadata
        self.downloaders = []

    def select_services_for_aoi(self, area_polygon: GeoSeries):
        """
        Automatically select the appropriate WMS services for the given AOI.

        Args:
            area_polygon: The polygon representing the area of interest.

        Returns:
            List[ImageDownloader]: A list of instantiated ImageDownloader objects.
        """
        selected_downloaders = []
        for metadata in self.wms_metadata:
            bounding_box = Polygon.from_bounds(*metadata['bounding_box'])
            if area_polygon.intersects(bounding_box).any():
                wms = ExtendedWebMapService(
                    url=metadata['url'],
                    version=metadata['version'],
                    resolution=metadata['resolution'],
                    layer_name=metadata['layer_name'],
                    crs=metadata['crs'],
                    format=metadata['format'],
                )
                wms.bounding_box = metadata['bounding_box']
                selected_downloaders.append(ImageDownloader(wms=wms, grid_spacing=metadata['resolution']))
        return selected_downloaders

    def preview_aoi(self, area_polygon: GeoSeries):
        """
        Provide a pre-download preview of the requested AOI.

        Args:
            area_polygon: The polygon representing the area of interest.

        Returns:
            dict: A dictionary containing estimated tile count, total data size, coverage diagnostics,
                  and an overview image for visual validation.
        """
        # Placeholder implementation for preview functionality
        return {
            "estimated_tile_count": 0,
            "total_data_size": "0 MB",
            "coverage_diagnostics": "No diagnostics available",
            "overview_image": None,
        }

    def download_aoi(self, area_polygon: GeoSeries, out_path: str):
        """
        Download all tiles for the given AOI using the appropriate WMS services.

        Args:
            area_polygon: The polygon representing the area of interest.
            out_path: The output path for the downloaded images.
        """
        # Select the appropriate services
        self.downloaders = self.select_services_for_aoi(area_polygon)

        # Use ThreadPoolExecutor for parallel downloads
        with ThreadPoolExecutor() as executor:
            futures = []
            for downloader in self.downloaders:
                bounding_box = Polygon.from_bounds(*downloader.wms.bounding_box)
                if area_polygon.intersects(bounding_box).any():
                    sub_area = area_polygon.intersection(bounding_box)
                    if not sub_area.is_empty.any():
                        sub_area = sub_area[sub_area.is_valid]
                        futures.append(
                            executor.submit(
                                downloader.download_images_from_polygon,
                                area_name="SubArea",
                                area_polygon=sub_area,
                                out_path=out_path,
                            )
                        )

            # Wait for all downloads to complete
            for future in futures:
                future.result()

class MultiServiceDownloader:
    """
    A class to manage multiple WMS services and download images for a given area.
    """
    def __init__(self, wms_metadata: list):
        self.wms_metadata = wms_metadata
        self.downloaders = []

    def download_images_for_area(self, area_polygon, out_path):
        """
        Instantiate downloaders for all WMS services whose bounding box intersects the area_polygon
        and trigger their download_images_from_polygon method.
        """
        self.downloaders = []
        for metadata in self.wms_metadata:
            bounding_box = Polygon.from_bounds(*metadata['bounding_box'])
            if area_polygon.intersects(bounding_box).any():
                wms = ExtendedWebMapService(
                    url=metadata['url'],
                    version=metadata['version'],
                    resolution=metadata['resolution'],
                    layer_name=metadata['layer_name'],
                    crs=metadata['crs'],
                    format=metadata['format'],
                )
                wms.bounding_box = metadata['bounding_box']
                downloader = ImageDownloader(wms=wms, grid_spacing=metadata['resolution'])
                self.downloaders.append(downloader)
                # Download images for the intersection area
                sub_area = area_polygon.intersection(bounding_box)
                if not sub_area.is_empty.any():
                    sub_area = sub_area[sub_area.is_valid]
                    downloader.download_images_from_polygon(
                        area_name="SubArea",
                        area_polygon=sub_area,
                        out_path=out_path,
                    )
