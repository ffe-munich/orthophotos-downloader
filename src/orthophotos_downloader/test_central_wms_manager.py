import unittest
from shapely.geometry import Polygon
from geopandas import GeoSeries
from orthophotos_downloader.data_scraping.image_download import CentralWMSManager

class TestCentralWMSManager(unittest.TestCase):
    def setUp(self):
        """Set up test data and WMS metadata."""
        self.wms_metadata = [
            {
                'url': 'https://geoservices.bayern.de/od/wms/dop/v1/dop20?',
                'version': '1.1.1',
                'resolution': 0.2,
                'layer_name': 'by_dop20c',
                'crs': 'EPSG:25832',
                'format': 'image/tiff',
                'bounding_box': (10, 10, 20, 20),
            },
            {
                'url': 'https://owsproxy.lgl-bw.de/owsproxy/ows/WMS_LGL-BW_ATKIS_DOP_20_C?',
                'version': '1.1.1',
                'resolution': 0.2,
                'layer_name': 'IMAGES_DOP_20_RGB',
                'crs': 'EPSG:25832',
                'format': 'image/jpeg',
                'bounding_box': (15, 15, 25, 25),
            },
        ]

        self.area_polygon = GeoSeries([Polygon([(12, 12), (18, 12), (18, 18), (12, 18)])], crs="EPSG:25832")
        self.out_path = '/tmp/test_output'

    def test_select_services_for_aoi(self):
        """Test that the correct WMS services are selected for the AOI."""
        manager = CentralWMSManager(self.wms_metadata)
        downloaders = manager.select_services_for_aoi(self.area_polygon)

        # Check that two downloaders were instantiated
        self.assertEqual(len(downloaders), 2)

    def test_preview_aoi(self):
        """Test the pre-download preview functionality."""
        manager = CentralWMSManager(self.wms_metadata)
        preview = manager.preview_aoi(self.area_polygon)

        # Check that the preview contains the expected keys
        self.assertIn("estimated_tile_count", preview)
        self.assertIn("total_data_size", preview)
        self.assertIn("coverage_diagnostics", preview)
        self.assertIn("overview_image", preview)

    def test_download_aoi(self):
        """Test the download functionality for the AOI."""
        manager = CentralWMSManager(self.wms_metadata)
        manager.download_aoi(self.area_polygon, self.out_path)

        # Check that the downloaders were instantiated
        self.assertEqual(len(manager.downloaders), 2)

if __name__ == '__main__':
    unittest.main()