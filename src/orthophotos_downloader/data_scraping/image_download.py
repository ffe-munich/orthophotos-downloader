import imageio.v3 as io
import logging
import numpy as np
import rasterio
import json

import math
from numbers import Number

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
from shapely.geometry import Polygon, mapping, shape, box
from tenacity import retry, stop_after_attempt, wait_fixed, before_sleep_log
from rasterio.merge import merge
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
        return {
            k: v if isinstance(v, Number) else str(v) for k, v in self.__dict__.items()
        }


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
            self.images = [
                Image(**i) if isinstance(i, dict) else i for i in self.images
            ]

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
        self,
        url: str,
        version: str,
        resolution: float,
        layer_name: str,
        crs: str,
        format: str,
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
            layers=[self.layer_name],
            srs=self.crs,
            bbox=bbox,
            size=size,
            format=self.format,
        )

    def to_dict(self) -> dict:
        """Return a serializable dictionary representation of the object."""
        r = {
            k: v if isinstance(v, Number) else str(v) for k, v in self.__dict__.items()
        }
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
            logger.error(
                f"Expected GeoSeries for argument '{argname}', but got {type(geoseries)}."
            )
            raise ValueError(f"Expected GeoSeries for '{argname}'.")

        # make sure the GeoSeries only contains one polygon
        if len(geoseries) != 1:
            logger.error(
                f"Expected GeoSeries of length 1 for argument '{argname}', but got GeoSeries of length {geoseries.length}."
            )
            raise ValueError(
                f"Expected GeoSeries of length 1 for argument '{argname}'."
            )

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
            logger.info(
                f"Filtered images (using the provided mask): {len_before - len(grid)}"
            )
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
        filename_prefix: str = "image",
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
            filename_prefix: The prefix for the downloaded image filenames.

        Returns:
            An AreaDataset object containing (among others) a list of downloaded images. When single image downloads fail, the method still finishes, but failed
            images are not stored to disk and they are included in the AreaDataset as Image instances with empty paths.
        """

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

            # Imagename based on lower left corner of the tile
            ulx = int(tile.geometry.bounds[0])  # x_min
            uly = int(tile.geometry.bounds[1])  # y_min
            filename = f"{filename_prefix}_32_{ulx}_{uly}.{file_extension}"
            img_path = Path(out_path) / filename
            try:
                images.append(
                    ImageDownloader.download_single_image(
                        img_path=img_path,
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
                logger.error(
                    f"Error downloading image {i+1}. Append empty image to images list..."
                )
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
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_fixed(10),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def download_single_image(
        img_path: Path,
        bounding_box: Polygon,
        wms: ExtendedWebMapService,
        width_px: int,
        height_px: int,
        mask: Optional[GeoSeries] = None,
        driver: str = "GTiff",
        max_tile_size_px: int = 2500,
    ) -> Image:
        """
        Downloads a single image from a Web Map Service (WMS) using the specified parameters.

        If the requested image size (in pixels) exceeds the max_tile_size_px threshold in either
        dimension, the image is automatically split into smaller tiles, downloaded individually,
        and merged into a single image file. Otherwise, the image is downloaded directly in one request.

        Args:
            img_path: The output path where the final image will be saved.
            bounding_box: A shapely Polygon defining the extent of the image to download.
            wms: An instance of ExtendedWebMapService containing WMS settings.
            width_px: The total width of the image in pixels.
            height_px: The total height of the image in pixels.
            mask: An optional GeoSeries (of length 1) to generate a binary mask for the image.
            driver: The rasterio driver to use (default is "GTiff").
            max_tile_size_px: Maximum allowed image width or height (in pixels) per WMS request.

        Returns:
            An Image instance with metadata about the downloaded (and possibly merged) image.

        Raises:
            Any exception raised during download or file writing is not handled here and should
            be caught by the calling method.
        """
        if width_px <= max_tile_size_px and height_px <= max_tile_size_px:
            return ImageDownloader._download_tile(
                img_path, bounding_box, wms, width_px, height_px, mask, driver
            )
        else:
            return ImageDownloader._download_tiled_image(
                img_path,
                bounding_box,
                wms,
                width_px,
                height_px,
                mask,
                driver,
                max_tile_size_px,
            )

    @staticmethod
    def _download_tile(
        img_path: Path,
        bounding_box: Polygon,
        wms: ExtendedWebMapService,
        width_px: int,
        height_px: int,
        mask: Optional[GeoSeries] = None,
        driver: str = "GTiff",
    ) -> Image:
        """
        Downloads a single image tile from a WMS server and saves it as a GeoTIFF file.

        This method sends a GetMap request to the given WMS using the specified bounding box
        and pixel dimensions. It saves the result as a 3-band GeoTIFF. Optionally, it can also
        generate and save a binary mask based on an input geometry.

        Args:
            img_path: The output path where the image will be saved.
            bounding_box: A shapely Polygon defining the area to download.
            wms: An ExtendedWebMapService instance with WMS configuration.
            width_px: The width of the image in pixels.
            height_px: The height of the image in pixels.
            mask: An optional GeoSeries (of length 1) for generating a binary mask image.
            driver: The rasterio driver to use (e.g., "GTiff").

        Returns:
            An Image instance with metadata about the downloaded image.

        Raises:
            Any exception raised during the download or file writing process is not caught here
            and should be handled by the calling function.
        """
        start_time = perf_counter()
        response = wms.getmap(
            bbox=bounding_box.bounds,
            size=(width_px, height_px),
        )
        result = response.read()
        img = io.imread(result, index=None)[:, :, :3]
        mask_path = (
            img_path.with_stem(f"{img_path.stem}_mask") if mask is not None else None
        )
        upper_left_x = bounding_box.bounds[0]
        upper_left_y = bounding_box.bounds[3]
        metadata = {
            "driver": driver,
            "dtype": rasterio.uint8,
            "nodata": None,
            "width": width_px,
            "height": height_px,
            "count": 3,
            "crs": rasterio.crs.CRS.from_string(wms.crs),
            "transform": from_origin(
                upper_left_x, upper_left_y, wms.resolution, wms.resolution
            ),
        }
        with rasterio.open(img_path, "w", **metadata) as dst:
            dst.write(img.transpose((2, 0, 1)))
        if mask is not None:
            mask_img = rasterize(
                [(mapping(mask.iloc[0].intersection(bounding_box)), 1)],
                out_shape=(height_px, width_px),
                transform=metadata["transform"],
                fill=0,
                dtype=rasterio.uint8,
            )
            metadata.update({"count": 1})
            with rasterio.open(mask_path, "w", nbits=1, **metadata) as dst:
                dst.write(mask_img, 1)
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
    def _download_tiled_image(
        img_path: Path,
        bounding_box: Polygon,
        wms: ExtendedWebMapService,
        width_px: int,
        height_px: int,
        mask: Optional[GeoSeries],
        driver: str,
        max_tile_size_px: int,
    ) -> Image:
        """
        Downloads a large image by splitting it into smaller subtiles, downloading each tile individually,
        and merging them into a single image file.

        This method is used when a WMS image request exceeds the maximum allowed pixel dimensions.
        It calculates a regular grid of smaller bounding boxes that cover the requested area,
        downloads each one separately, and assembles them into a seamless image.

        Args:
            img_path: The final output path where the merged image will be saved.
            bounding_box: A shapely Polygon defining the area to download.
            wms: An instance of ExtendedWebMapService with WMS configuration.
            width_px: Total width of the requested image in pixels.
            height_px: Total height of the requested image in pixels.
            mask: An optional GeoSeries for applying a mask (not supported within tiled download yet).
            driver: The rasterio driver to use for saving the image (e.g., "GTiff").
            max_tile_size_px: The maximum allowed tile width or height (in pixels) per individual WMS request.

        Returns:
            An Image instance containing metadata for the final, merged image.

        Notes:
            - This method assumes the input bounding box is in the same CRS as the WMS.
            - Temporary subtile files are stored on disk and deleted after merging.
            - Masking is currently not applied on subtile level; provide a postprocessing step if needed.
        """

        tile_res = wms.resolution
        total_width_m = width_px * tile_res
        total_height_m = height_px * tile_res

        upper_left_x = bounding_box.bounds[0]
        upper_left_y = bounding_box.bounds[3]

        cols = math.ceil(width_px / max_tile_size_px)
        rows = math.ceil(height_px / max_tile_size_px)

        tile_paths = []
        start_time = perf_counter()

        for row in range(rows):
            for col in range(cols):
                # Berechne die BoundingBox der Subkachel
                x0 = upper_left_x + col * max_tile_size_px * tile_res
                y0 = upper_left_y - row * max_tile_size_px * tile_res
                x1 = min(x0 + max_tile_size_px * tile_res, bounding_box.bounds[2])
                y1 = max(y0 - max_tile_size_px * tile_res, bounding_box.bounds[1])

                sub_bbox = box(x0, y1, x1, y0)
                sub_width = min(max_tile_size_px, width_px - col * max_tile_size_px)
                sub_height = min(max_tile_size_px, height_px - row * max_tile_size_px)

                subtile_path = img_path.parent / f"{img_path.stem}_sub_{row}_{col}.tiff"
                sub_image = ImageDownloader._download_tile(
                    img_path=subtile_path,
                    bounding_box=sub_bbox,
                    wms=wms,
                    width_px=sub_width,
                    height_px=sub_height,
                    mask=None,
                    driver=driver,
                )
                tile_paths.append(subtile_path)

        # Öffne alle Subtiles als DatasetReader
        datasets = [rasterio.open(p) for p in tile_paths]

        # Füge die Subkacheln zu einem Bild zusammen
        merged_img, merged_transform = merge(datasets)

        # Metadaten anpassen
        meta = datasets[0].meta.copy()
        meta.update(
            {
                "height": merged_img.shape[1],
                "width": merged_img.shape[2],
                "transform": merged_transform,
            }
        )

        # Schreibe zusammengeführtes Bild
        with rasterio.open(img_path, "w", **meta) as dst:
            dst.write(merged_img)

        # Optional: temporäre Subkacheln löschen
        for ds in datasets:
            ds.close()
        for p in tile_paths:
            p.unlink(missing_ok=True)

        return Image(
            image_path=img_path,
            mask_path=None,
            upper_left_x=upper_left_x,
            upper_left_y=upper_left_y,
            width_m=total_width_m,
            height_m=total_height_m,
            width_px=width_px,
            height_px=height_px,
            resolution_m=tile_res,
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
            logger.warning(
                f"Path '{dir_path}' passed to delete_images() is already empty."
            )

        # check if dir_path contains files other than images
        if any([f.suffix not in [".png", ".tiff"] for f in dir_path.iterdir()]):
            logger.error(
                f"Path '{dir_path}' passed to delete_images() contains not only images."
            )
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
    ) -> (
        GeoDataFrame
    ):  # TODO this function does not generates well to any other coordinate system
        """
        Creates a grid of squares that fully covers the specified area of interest and is alligned with utm coordinate system.

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

        # snap the points to the grid, whichs cell size is defined by grid_spacing
        x_coords = [round(x / grid_spacing) * grid_spacing for x in x_coords]
        y_coords = [round(y / grid_spacing) * grid_spacing for y in y_coords]

        # ensure to cover the whole area by expanding the grid by one grid_spacing in each direction
        x_coords = [x_coords[0] - grid_spacing] + x_coords + [x_coords[-1] + grid_spacing]
        y_coords = [y_coords[0] - grid_spacing] + y_coords + [y_coords[-1] + grid_spacing]

        # Create squares around each point
        grid = []
        for x in range(int(minx), int(maxx), grid_spacing):
            for y in range(int(miny), int(maxy), grid_spacing):
                cell = box(x, y, x + grid_spacing, y + grid_spacing)
                if buffered_area.intersects(cell):
                    grid.append(cell)

        return GeoDataFrame(geometry=grid)

    def to_dict(self) -> dict:
        """Return a serializable dictionary representation of the ImageDownloader object."""
        r = {
            k: v if isinstance(v, Number) else str(v) for k, v in self.__dict__.items()
        }
        r["wms"] = self.wms.to_dict()
        return r

    def merge_rgb_cir_to_rgbi(rgb_path: Path, cir_path: Path, out_path: Path) -> None:
        """
        Combines a 3-band RGB image and a CIR image (with NIR in band 3)
        into a single 4-band RGBI GeoTIFF file.

        Args:
            rgb_path: Path to the 3-band RGB GeoTIFF.
            cir_path: Path to the 3-band CIR GeoTIFF (NIR expected in band 3).
            out_path: Path where the resulting 4-band image will be saved.

        Raises:
            AssertionError: If image sizes don't match.
        """

        with rasterio.open(rgb_path) as rgb_ds, rasterio.open(cir_path) as cir_ds:
            rgb = rgb_ds.read([1, 2, 3])  # RGB bands
            nir = cir_ds.read(1)  # NIR from CIR (band 1)

            assert rgb.shape[1:] == nir.shape, "RGB and CIR dimensions don't match"

            rgbi = np.vstack((rgb, nir[np.newaxis, :, :]))  # Add NIR as 4th band

            profile = rgb_ds.profile.copy()
            profile.update(count=4)

            with rasterio.open(out_path, "w", **profile) as dst:
                dst.write(rgbi)


class RGBIImageDownloader:
    """
    A downloader class that combines RGB and CIR image downloads into a single RGBI image.

    This class wraps two ImageDownloader instances (one for RGB and one for CIR)
    and provides a method to download matching tiles from both services, then merge them
    into a 4-band (RGBI) GeoTIFF.
    """

    def __init__(
        self, rgb_downloader: ImageDownloader, cir_downloader: ImageDownloader
    ):
        """
        Initializes the RGBIImageDownloader with separate RGB and CIR downloaders.

        Args:
            rgb_downloader: An ImageDownloader configured for RGB imagery.
            cir_downloader: An ImageDownloader configured for CIR imagery.

        Raises:
            AssertionError: If the two downloaders do not use the same grid spacing.
        """
        assert (
            rgb_downloader.grid_spacing == cir_downloader.grid_spacing
        ), "Grid spacings must match"
        self.rgb_downloader = rgb_downloader
        self.cir_downloader = cir_downloader
        self.grid_spacing = rgb_downloader.grid_spacing

    def download_rgbi_images_from_polygon(
        self,
        area_name: str,
        area_polygon: GeoSeries,
        out_path: Path | str,
        buffer_size: int = 0,
        mask: Optional[GeoSeries] = None,
        driver: str = "GTiff",
        file_extension: str = "tiff",
    ) -> AreaDataset:
        """
        Downloads RGB and CIR tiles for a given area and merges them into RGBI images.

        Args:
            area_name: Name of the dataset/area.
            area_polygon: GeoSeries containing a single polygon representing the AOI.
            out_path: Directory where output images will be saved.
            buffer_size: Optional buffer (in meters) around the AOI.
            mask: Optional mask geometry to clip downloaded data.
            driver: Rasterio driver to use (default is GTiff).
            file_extension: File extension for saved images (e.g. 'tiff').

        Returns:
            AreaDataset object containing metadata about the downloaded RGBI images.
        """

        out_path = Path(out_path)
        grid = self.rgb_downloader._prepare_image_download(
            area_polygon, out_path, buffer_size, mask
        )
        area_polygon = area_polygon.iloc[0]

        result_obj = AreaDataset(area_name, area_polygon, buffer_size, out_path)
        images = []

        for i, tile in enumerate(grid.itertuples()):
            start_time = perf_counter()
            ulx = int(tile.geometry.bounds[0])
            uly = int(tile.geometry.bounds[1])
            prefix = f"{ulx}_{uly}"

            temp_path = out_path / "temp"
            temp_path.mkdir(parents=True, exist_ok=True)

            rgb_path = temp_path / f"RGB_32_{prefix}.{file_extension}"
            cir_path = temp_path / f"CIR_32_{prefix}.{file_extension}"
            rgbi_path = out_path / f"RGBI_32_{prefix}.{file_extension}"

            try:
                # Download RGB tile
                rgb_img = self.rgb_downloader.download_single_image(
                    img_path=rgb_path,
                    bounding_box=tile.geometry,
                    wms=self.rgb_downloader.wms,
                    width_px=self.rgb_downloader.width_px,
                    height_px=self.rgb_downloader.height_px,
                    mask=mask,
                    driver=driver,
                )

                # Download CIR tile
                cir_img = self.cir_downloader.download_single_image(
                    img_path=cir_path,
                    bounding_box=tile.geometry,
                    wms=self.cir_downloader.wms,
                    width_px=self.cir_downloader.width_px,
                    height_px=self.cir_downloader.height_px,
                    mask=None,
                    driver=driver,
                )

                # Merge into RGBI
                ImageDownloader.merge_rgb_cir_to_rgbi(rgb_path, cir_path, rgbi_path)

                # Clean up temporary files
                ImageDownloader.delete_images(temp_path)

                # Save image metadata
                images.append(
                    Image(
                        image_path=rgbi_path,
                        mask_path=None,
                        upper_left_x=ulx,
                        upper_left_y=tile.geometry.bounds[3],
                        download_time=perf_counter() - start_time,
                        width_m=self.grid_spacing,
                        height_m=self.grid_spacing,
                        width_px=self.rgb_downloader.width_px,
                        height_px=self.rgb_downloader.height_px,
                        resolution_m=self.rgb_downloader.wms.resolution,
                        crs=self.rgb_downloader.wms.crs,
                    )
                )

            except Exception as e:
                logger.error(f"Error downloading RGBI image for tile {ulx}, {uly}")
                logger.exception(e)

        result_obj.images = images
        return result_obj
