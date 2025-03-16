import os
from unittest import TestCase

from soil_analysis.domain.valueobject.capturelocation import CaptureLocation
from soil_analysis.domain.valueobject.photo.androidphoto import AndroidPhoto


class TestAndroidPhoto(TestCase):
    def setUp(self):
        script_directory = os.path.dirname(os.path.abspath(__file__))
        self.file_path = r"./android/JA中_all.jpg"
        self.android_photo = AndroidPhoto(
            os.path.join(script_directory, self.file_path)
        )
        self.android_photo.exif_data = self.android_photo._extract_exif_data()

    def test_extract_date(self):
        # 正常な値のテスト
        expected_date = "2023-08-27"
        actual_date = self.android_photo._extract_date()
        self.assertEqual(expected_date, actual_date)

        # GPS GPSDate が None の場合のテスト
        self.android_photo.exif_data["Image DateTime"] = None
        with self.assertRaises(ValueError):
            self.android_photo._extract_date()

    def test_extract_location(self):
        # 正常な値のテスト
        expected_location = CaptureLocation(137.8266552, 34.6942567)  # xarvio based
        actual_location = self.android_photo._extract_location()
        self.assertAlmostEqual(
            expected_location.adjusted_position.to_tuple()[0],
            actual_location.adjusted_position.to_tuple()[0],
            delta=0.001,
        )
        self.assertAlmostEqual(
            expected_location.adjusted_position.to_tuple()[1],
            actual_location.adjusted_position.to_tuple()[1],
            delta=0.001,
        )

        # GPS GPSLongitude が None の場合のテスト
        self.android_photo.exif_data["GPS GPSLongitude"] = None
        with self.assertRaises(ValueError):
            self.android_photo._extract_location()

        # GPS GPSLatitude が None の場合のテスト
        self.android_photo.exif_data["GPS GPSLatitude"] = None
        with self.assertRaises(ValueError):
            self.android_photo._extract_location()
