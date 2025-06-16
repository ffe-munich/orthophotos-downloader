import unittest
from shapely.geometry import Polygon
from geopandas import GeoSeries
from orthophotos_downloader.data_scraping.image_download import MultiServiceDownloader

class TestMultiServiceDownloader(unittest.TestCase):
    def setUp(self):
        """Set up test data and WMS metadata for Ulm/Neu-Ulm area (Bayern & Baden-Württemberg)."""
        # Realistische Bounding-Boxen für Bayern und Baden-Württemberg im Ulm/Neu-Ulm Bereich (EPSG:25832, grob)
        self.wms_metadata = [
            {
                'url': 'https://geoservices.bayern.de/od/wms/dop/v1/dop20?',
                'version': '1.1.1',
                'resolution': 200,
                'layer_name': 'by_dop20c',
                'crs': 'EPSG:25832',
                'format': 'image/tiff',
                'bounding_box': (540000, 5355000, 555000, 5370000),  # Bayern
            },
            {
                'url': 'https://owsproxy.lgl-bw.de/owsproxy/ows/WMS_LGL-BW_ATKIS_DOP_20_C?',
                'version': '1.1.1',
                'resolution': 200,
                'layer_name': 'IMAGES_DOP_20_RGB',
                'crs': 'EPSG:25832',
                'format': 'image/jpeg',
                'bounding_box': (540000, 5355000, 555000, 5370000),  # Baden-Württemberg
            },
        ]

        # Polygon um Ulm/Neu-Ulm, das beide Bundesländer schneidet (EPSG:25832, grob)
        self.area_polygon = GeoSeries([
            Polygon([
                (545000, 5360000),  # westlich von Ulm
                (547000, 5360000),  # nördlich von Ulm
                (547000, 5362000),  # östlich von Neu-Ulm
                (545000, 5362000),  # südlich von Ulm
            ])
        ], crs="EPSG:25832")
        self.out_path = '/tmp/test_output_ulm'

    def test_download_images_for_area(self):
        """Test that the correct WMS services are instantiated and used."""
        downloader = MultiServiceDownloader(self.wms_metadata)

        # Debug: Validate area_polygon and bounding boxes
        print("Area Polygon:", self.area_polygon)
        for metadata in self.wms_metadata:
            bounding_box = Polygon.from_bounds(*metadata['bounding_box'])
            print("Bounding Box:", bounding_box)

        downloader.download_images_for_area(self.area_polygon, self.out_path)

        # Check that two downloaders were instantiated
        self.assertEqual(len(downloader.downloaders), 2)

        # Check that the bounding boxes of the instantiated downloaders match the metadata
        bounding_boxes = [
            Polygon.from_bounds(*d.wms.bounding_box) for d in downloader.downloaders
        ]
        self.assertTrue(any(b.intersects(self.area_polygon.iloc[0]) for b in bounding_boxes))

if __name__ == '__main__':
    unittest.main()