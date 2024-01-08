import os
from unittest import TestCase

from soil_analysis.domain.service.photoprocessingservice import PhotoProcessingService
from soil_analysis.domain.valueobject.capturelocation import CaptureLocation
from soil_analysis.domain.valueobject.coords.capturelocationcoords import CaptureLocationCoords
from soil_analysis.domain.valueobject.coords.landcoords import LandCoords
from soil_analysis.domain.valueobject.land import Land
from soil_analysis.domain.valueobject.landcandidates import LandCandidates


class TestPhotoProcessingService(TestCase):
    def setUp(self) -> None:
        self.land1 = Land('ススムA1', '137.6489657,34.7443565 137.6491266,34.744123 137.648613,34.7438929 '
                                      '137.6484413,34.7441175 137.6489657,34.7443565')
        self.land2 = Land('ススムA2', '137.649128,34.7441119 137.6492862,34.7438795 137.6487833,34.7436526 '
                                      '137.6486224,34.7438861 137.649128,34.7441119')
        self.land3 = Land('ススムA3', '137.6492809,34.743865 137.6494646,34.7436029 137.6489644,34.7433683 '
                                      '137.6487806,34.7436403 137.6492809,34.743865')
        self.land4 = Land('ススムA4', '137.6489738,34.7433604 137.6494633,34.7435774 137.6497127,34.7432096 '
                                      '137.6492192,34.7429904 137.6489738,34.7433604')
        self.land_candidates = LandCandidates([self.land1, self.land2, self.land3, self.land4])

        script_directory = os.path.dirname(os.path.abspath(__file__))
        self.photo_paths = [
            os.path.join(script_directory, r"./android/ススムＢ1_right.jpg"),
            os.path.join(script_directory, r"./android/ススムB2.jpg")
        ]

    def test_calculate_distance(self):
        coords1 = CaptureLocationCoords(137.6492809, 34.743865)  # ススムA3撮影座標
        coords2 = LandCoords("137.6487935,34.744671")  # ススムA3撮影座標から100mの場所（Landで代用）
        expected_distance = 100.0  # 期待される距離（100メートル）
        distance = PhotoProcessingService.calculate_distance(coords1, coords2)
        self.assertAlmostEqual(expected_distance, distance, delta=0.1)  # 許容誤差を指定

    def test_find_nearest_land_a1(self):
        # 撮影位置は ススムA1 正面
        photo_coords = CaptureLocation(137.64905, 34.74424)
        service = PhotoProcessingService()
        nearest_land = service.find_nearest_land(photo_coords, self.land_candidates)
        self.assertEqual(self.land1, nearest_land)

    def test_find_nearest_land_a2(self):
        # 撮影位置は ススムA2 正面
        photo_coords = CaptureLocation(137.64921, 34.744)
        service = PhotoProcessingService()
        nearest_land = service.find_nearest_land(photo_coords, self.land_candidates)
        self.assertEqual(self.land2, nearest_land)

    def test_find_nearest_land_a3(self):
        # 撮影位置は ススムA3 正面
        photo_coords = CaptureLocation(137.64938, 34.74374)
        service = PhotoProcessingService()
        nearest_land = service.find_nearest_land(photo_coords, self.land_candidates)
        self.assertEqual(self.land3, nearest_land)

    def test_find_nearest_land_a4(self):
        # 撮影位置は ススムA4 正面
        photo_coords = CaptureLocation(137.6496, 34.7434)
        service = PhotoProcessingService()
        nearest_land = service.find_nearest_land(photo_coords, self.land_candidates)
        self.assertEqual(self.land4, nearest_land)

    def test_process_photos(self):
        service = PhotoProcessingService()
        processed_photos = service.process_photos(self.photo_paths, self.land_candidates)
        # 期待される処理後の写真のリストと一致するか検証する ススムは 2023/6/18 のグーグルフォトにある
        script_directory = os.path.dirname(os.path.abspath(__file__))
        expected_processed_photos = [
            os.path.join(script_directory, "./android/ススムＢ1_right.jpg"),
            os.path.join(script_directory, "./android/ススムB2.jpg")
        ]
        self.assertEqual(expected_processed_photos, processed_photos)
