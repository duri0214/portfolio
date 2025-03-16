import os
from unittest import TestCase
from unittest.mock import MagicMock, patch

from lib.geo.valueobject.coord import XarvioCoord
from soil_analysis.domain.service.photoprocessingservice import PhotoProcessingService
from soil_analysis.domain.valueobject.capturelocation import CaptureLocation
from soil_analysis.domain.valueobject.land import LandLocation
from soil_analysis.domain.valueobject.landcandidates import LandCandidates
from soil_analysis.domain.valueobject.photo_land_association import PhotoLandAssociation


class TestPhotoProcessingService(TestCase):
    """PhotoProcessingServiceクラスのテストスイート。

    写真と圃場を自動的に紐づける機能を検証するテストスイートです。
    複数の圃場（ススムA1〜A4）が隣接する環境で、各写真の撮影位置から
    どの圃場を撮影したものかを正確に特定できるかをテストします。

    主な検証項目:
    1. 撮影位置と圃場の距離計算の精度
    2. 最寄りの圃場を正しく特定する機能
    3. 複数の写真を処理し、それぞれ適切な圃場と紐づけられるか

    テストデータとして「ススムA1」〜「ススムA4」という4つの圃場と、
    それぞれの圃場の正面から撮影したと想定される座標を使用しています。
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
        photo_spot = XarvioCoord(longitude=137.6492809, latitude=34.743865)
        reference_point = LandLocation(
            "137.6487935,34.744671",
            "ススムA3撮影座標から100mの場所",
        )
        expected_distance = 100.0
        distance = PhotoProcessingService.calculate_distance(
            photo_spot, reference_point.center
        )
        self.assertAlmostEqual(expected_distance, distance, delta=0.1)

    def test_find_nearest_land_a1(self):
        """ススムA1圃場の正面からの撮影で、正しく最寄りの圃場が特定できることをテストします。

        撮影位置をススムA1の正面に設定し、find_nearest_land関数が
        ススムA1を最も近い圃場として正しく特定できることを検証します。
        """
        photo_spot = CaptureLocation(longitude=137.64905, latitude=34.74424)
        service = PhotoProcessingService()
        nearest_land = service.find_nearest_land(photo_spot, self.land_candidates)
        self.assertEqual(self.land1, nearest_land)

    def test_find_nearest_land_a2(self):
        """ススムA2圃場の正面からの撮影で、正しく最寄りの圃場が特定できることをテストします。

        撮影位置をススムA2の正面に設定し、find_nearest_land関数が
        ススムA2を最も近い圃場として正しく特定できることを検証します。
        """
        photo_spot = CaptureLocation(longitude=137.64921, latitude=34.744)
        service = PhotoProcessingService()
        nearest_land = service.find_nearest_land(photo_spot, self.land_candidates)
        self.assertEqual(self.land2, nearest_land)

    def test_find_nearest_land_a3(self):
        """ススムA3圃場の正面からの撮影で、正しく最寄りの圃場が特定できることをテストします。

        撮影位置をススムA3の正面に設定し、find_nearest_land関数が
        ススムA3を最も近い圃場として正しく特定できることを検証します。
        """
        photo_spot = CaptureLocation(longitude=137.64938, latitude=34.74374)
        service = PhotoProcessingService()
        nearest_land = service.find_nearest_land(photo_spot, self.land_candidates)
        self.assertEqual(self.land3, nearest_land)

    def test_find_nearest_land_a4(self):
        """ススムA4圃場の正面からの撮影で、正しく最寄りの圃場が特定できることをテストします。

        撮影位置をススムA4の正面に設定し、find_nearest_land関数が
        ススムA4を最も近い圃場として正しく特定できることを検証します。
        """
        photo_spot = CaptureLocation(137.6496, 34.7434)
        service = PhotoProcessingService()
        nearest_land = service.find_nearest_land(photo_spot, self.land_candidates)
        self.assertEqual(self.land4, nearest_land)

    def test_process_photos(self):
        """複数写真の処理と圃場紐づけ機能をテストします。"""
        # 圃場の位置をGoogleマップで確認できる形式で出力
        for i, land in enumerate([self.land1, self.land2, self.land3, self.land4]):
            print(f"{land.name} | Google Maps: {land.center.to_google().to_str()}")

        # 写真の位置を設定（azimuthは GoogleMaps で圃場中心方向に向けた値を特定したもの）
        # land1に近い位置を設定
        photo1_lng = 137.649086  # land1に近い経度
        photo1_lat = 34.744268  # land1に近い緯度
        capture_loc1 = CaptureLocation(
            longitude=photo1_lng, latitude=photo1_lat, azimuth=250
        )
        print(f"撮影位置1: {capture_loc1}")

        # land3に近い位置を設定
        photo2_lng = 137.649407  # land3に近い経度
        photo2_lat = 34.743749  # land3に近い緯度
        capture_loc2 = CaptureLocation(
            longitude=photo2_lng, latitude=photo2_lat, azimuth=250
        )
        print(f"撮影位置2: {capture_loc2}")

        # AndroidPhotoクラスのモック
        with patch(
            "soil_analysis.domain.valueobject.photo.androidphoto.AndroidPhoto"
        ) as mock_android_photo:
            # 1枚目の写真のモック設定
            mock_instance1 = MagicMock()
            mock_instance1.location = capture_loc1

            # 2枚目の写真のモック設定
            mock_instance2 = MagicMock()
            mock_instance2.location = capture_loc2

            # サイド・エフェクト設定
            mock_android_photo.side_effect = [mock_instance1, mock_instance2]

            # テスト対象のメソッド実行
            service = PhotoProcessingService()
            result = service.process_photos(self.photo_paths, self.land_candidates)

            # どの圃場が選ばれたかを出力
            print(
                f"撮影位置1から選択された圃場({result[0].nearest_land.name}): {result[0].nearest_land.center.to_google().to_str()} | 距離: {result[0].distance}m"
            )
            print(
                f"撮影位置2から選択された圃場({result[1].nearest_land.name}): {result[1].nearest_land.center.to_google().to_str()} | 距離: {result[1].distance}m"
            )

            # 結果の検証
            self.assertEqual(len(result), 2)
            self.assertIsInstance(result[0], PhotoLandAssociation)
            self.assertIsInstance(result[1], PhotoLandAssociation)
            self.assertEqual(self.photo_paths[0], result[0].photo_path)
            self.assertEqual(self.photo_paths[1], result[1].photo_path)

            # 両方の写真がland1に関連付けられていることを確認
            self.assertEqual(self.land1, result[0].nearest_land)
            self.assertEqual(self.land3, result[1].nearest_land)

            self.assertIsNotNone(result[0].distance)
            self.assertIsNotNone(result[1].distance)
