import os
from unittest import TestCase

from soil_analysis.domain.valueobject.capturelocation import CaptureLocation
from soil_analysis.domain.valueobject.photo.iphonephoto import IphonePhoto


class TestIphonePhoto(TestCase):
    def setUp(self):
        script_directory = os.path.dirname(os.path.abspath(__file__))
        self.file_path = r"./iphone/IMG_1315_left.jpeg"
        self.iphone_photo = IphonePhoto(os.path.join(script_directory, self.file_path))
        self.iphone_photo.exif_data = self.iphone_photo._extract_exif_data()

    def test_extract_date(self):
        # 正常な値のテスト
        expected_date = "2023-07-05"
        actual_date = self.iphone_photo._extract_date()
        self.assertEqual(expected_date, actual_date)

        # GPS GPSDate が None の場合のテスト
        self.iphone_photo.exif_data["Image DateTime"] = None
        with self.assertRaises(ValueError):
            self.iphone_photo._extract_date()

    def test_extract_location(self):
        # 正常な値のテスト
        expected_location = CaptureLocation(140.41932067, 35.80548371)  # xarvio based
        actual_location = self.iphone_photo._extract_location()
        self.assertAlmostEqual(expected_location.corrected.get_coords()[0], actual_location.corrected.get_coords()[0],
                               delta=0.001)
        self.assertAlmostEqual(expected_location.corrected.get_coords()[1], actual_location.corrected.get_coords()[1],
                               delta=0.001)

        # GPS GPSLongitude が None の場合のテスト
        self.iphone_photo.exif_data["GPS GPSLongitude"] = None
        with self.assertRaises(ValueError):
            self.iphone_photo._extract_location()

        # GPS GPSLatitude が None の場合のテスト
        self.iphone_photo.exif_data["GPS GPSLatitude"] = None
        with self.assertRaises(ValueError):
            self.iphone_photo._extract_location()

    def test_extract_azimuth(self):
        expected_azimuth = 195.21922317314022  # Exif Viewer based
        self.assertEqual(expected_azimuth, self.iphone_photo.azimuth)
