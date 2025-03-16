import os
from unittest import TestCase

from lib.geo.valueobject.coord import XarvioCoord
from soil_analysis.domain.service.photoprocessingservice import PhotoProcessingService
from soil_analysis.domain.valueobject.capturelocation import CaptureLocation
from soil_analysis.domain.valueobject.land import LandLocation
from soil_analysis.domain.valueobject.landcandidates import LandCandidates


class TestPhotoProcessingService(TestCase):
    """PhotoProcessingServiceクラスのテストスイート。

    複数の圃場を含む環境で、撮影位置から最も近い圃場を正確に特定する機能を検証します。
    テストデータとして「ススムA1」〜「ススムA4」という4つの圃場と、それぞれの圃場の正面から
    撮影したと想定される座標を使用しています。
    """

    def setUp(self) -> None:
        """テスト前の環境セットアップ。

        4つの圃場（ススムA1〜A4）の位置情報と、テスト用の写真ファイルパスを設定します。
        各圃場はポリゴン座標として定義され、LandLocationオブジェクトとして保持します。
        """
        self.land1 = LandLocation(
            "137.6489657,34.7443565 137.6491266,34.744123 137.648613,34.7438929 "
            "137.6484413,34.7441175 137.6489657,34.7443565",
            "ススムA1",
        )
        self.land2 = LandLocation(
            "137.649128,34.7441119 137.6492862,34.7438795 137.6487833,34.7436526 "
            "137.6486224,34.7438861 137.649128,34.7441119",
            "ススムA2",
        )
        self.land3 = LandLocation(
            "137.6492809,34.743865 137.6494646,34.7436029 137.6489644,34.7433683 "
            "137.6487806,34.7436403 137.6492809,34.743865",
            "ススムA3",
        )
        self.land4 = LandLocation(
            "137.6489738,34.7433604 137.6494633,34.7435774 137.6497127,34.7432096 "
            "137.6492192,34.7429904 137.6489738,34.7433604",
            "ススムA4",
        )
        self.land_candidates = LandCandidates(
            [self.land1, self.land2, self.land3, self.land4]
        )

        script_directory = os.path.dirname(os.path.abspath(__file__))
        self.photo_paths = [
            os.path.join(script_directory, r"./android/ススムＢ1_right.jpg"),
            os.path.join(script_directory, r"./android/ススムB2.jpg"),
        ]

    def test_calculate_distance(self):
        """座標間の距離計算機能をテストします。

        ススムA3の中心座標から約100メートル離れた場所までの距離を計算し、
        計算結果が期待値（約100メートル）に近いことを検証します。

        検証内容:
            - XarvioCoordとLandLocation間の距離計算の正確性
            - haversineライブラリを使った地球上の距離計算の精度
        """
        # ススムA3撮影座標
        coord1 = XarvioCoord(longitude=137.6492809, latitude=34.743865)
        # Landで代用
        coord2 = LandLocation("137.6487935,34.744671", "ススムA3撮影座標から100mの場所")
        expected_distance = 100.0  # 期待される距離（100メートル）
        distance = PhotoProcessingService.calculate_distance(coord1, coord2.center)
        self.assertAlmostEqual(expected_distance, distance, delta=0.1)  # 許容誤差を指定

    def test_find_nearest_land_a1(self):
        """ススムA1圃場の正面からの撮影で、正しく最寄りの圃場が特定できることをテストします。

        撮影位置をススムA1の正面に設定し、find_nearest_land関数が
        ススムA1を最も近い圃場として正しく特定できることを検証します。
        """
        # 撮影位置は ススムA1 正面
        photo_coord = CaptureLocation(longitude=137.64905, latitude=34.74424)
        service = PhotoProcessingService()
        nearest_land = service.find_nearest_land(photo_coord, self.land_candidates)
        self.assertEqual(self.land1, nearest_land)

    def test_find_nearest_land_a2(self):
        """ススムA2圃場の正面からの撮影で、正しく最寄りの圃場が特定できることをテストします。

        撮影位置をススムA2の正面に設定し、find_nearest_land関数が
        ススムA2を最も近い圃場として正しく特定できることを検証します。
        """
        # 撮影位置は ススムA2 正面
        photo_coord = CaptureLocation(longitude=137.64921, latitude=34.744)
        service = PhotoProcessingService()
        nearest_land = service.find_nearest_land(photo_coord, self.land_candidates)
        self.assertEqual(self.land2, nearest_land)

    def test_find_nearest_land_a3(self):
        """ススムA3圃場の正面からの撮影で、正しく最寄りの圃場が特定できることをテストします。

        撮影位置をススムA3の正面に設定し、find_nearest_land関数が
        ススムA3を最も近い圃場として正しく特定できることを検証します。
        """
        # 撮影位置は ススムA3 正面
        photo_coord = CaptureLocation(longitude=137.64938, latitude=34.74374)
        service = PhotoProcessingService()
        nearest_land = service.find_nearest_land(photo_coord, self.land_candidates)
        self.assertEqual(self.land3, nearest_land)

    def test_find_nearest_land_a4(self):
        """ススムA4圃場の正面からの撮影で、正しく最寄りの圃場が特定できることをテストします。

        撮影位置をススムA4の正面に設定し、find_nearest_land関数が
        ススムA4を最も近い圃場として正しく特定できることを検証します。
        """
        # 撮影位置は ススムA4 正面
        photo_coord = CaptureLocation(137.6496, 34.7434)
        service = PhotoProcessingService()
        nearest_land = service.find_nearest_land(photo_coord, self.land_candidates)
        self.assertEqual(self.land4, nearest_land)

    def test_process_photos(self):
        """写真処理機能の一連の流れをテストします。

        実際のAndroid写真ファイルパスを使用して、process_photos関数が
        適切に写真を処理し、予期された結果（処理済み写真のリスト）を
        返すことを検証します。

        このテストでは、実際の写真ファイルの位置情報を抽出し、最寄りの圃場を特定する
        エンドツーエンドの処理を検証しています。
        """
        service = PhotoProcessingService()
        processed_photos = service.process_photos(
            self.photo_paths, self.land_candidates
        )
        # 期待される処理後の写真のリストと一致するか検証する ススムは 2023/6/18 のグーグルフォトにある
        script_directory = os.path.dirname(os.path.abspath(__file__))
        expected_processed_photos = [
            os.path.join(script_directory, "./android/ススムＢ1_right.jpg"),
            os.path.join(script_directory, "./android/ススムB2.jpg"),
        ]
        self.assertEqual(expected_processed_photos, processed_photos)
