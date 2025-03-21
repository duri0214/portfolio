from unittest import TestCase
from unittest.mock import MagicMock, patch

from lib.geo.valueobject.coord import XarvioCoord
from soil_analysis.domain.service.photo_processing_service import PhotoProcessingService
from soil_analysis.domain.valueobject.capturelocation import CaptureLocation
from soil_analysis.domain.valueobject.land import LandLocation


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

        # 土地候補のリストを作成
        self.land_candidates = MagicMock()
        self.land_candidates.list = MagicMock(
            return_value=[self.land1, self.land2, self.land3, self.land4]
        )

        # テスト用の写真パス（実際のファイルパスは使わない）
        self.photo_paths = ["テスト写真パス1", "テスト写真パス2"]

        # AndroidPhotoとIphonePhotoのモックを設定
        self.android_photo_patcher = patch(
            "soil_analysis.domain.service.photo_processing_service.AndroidPhoto"
        )
        self.mock_android_photo = self.android_photo_patcher.start()

        # モック写真オブジェクトを作成
        self.android_photo_instance = MagicMock()
        self.mock_android_photo.return_value = self.android_photo_instance

        # 写真の位置情報を設定（実際の土地に近い位置）
        test_location = MagicMock()
        test_location.adjusted_position = MagicMock()
        test_location.adjusted_position.to_google = MagicMock()
        test_location.adjusted_position.to_google.return_value = MagicMock()
        test_location.adjusted_position.to_google.return_value.to_tuple = MagicMock(
            return_value=(34.7440, 137.6490)
        )

        self.android_photo_instance.location = test_location
        self.android_photo_instance.filepath = "テスト写真パス1"
        self.android_photo_instance.filename = "android_photo.jpg"
        self.android_photo_instance.date = "2023-08-27"

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
        photo_spot = CaptureLocation(
            XarvioCoord(longitude=137.64905, latitude=34.74424)
        )
        service = PhotoProcessingService()
        nearest_land = service.find_nearest_land(photo_spot, self.land_candidates)
        self.assertEqual(self.land1, nearest_land)

    def test_find_nearest_land_a2(self):
        """ススムA2圃場の正面からの撮影で、正しく最寄りの圃場が特定できることをテストします。

        撮影位置をススムA2の正面に設定し、find_nearest_land関数が
        ススムA2を最も近い圃場として正しく特定できることを検証します。
        """
        photo_spot = CaptureLocation(XarvioCoord(longitude=137.64921, latitude=34.744))
        service = PhotoProcessingService()
        nearest_land = service.find_nearest_land(photo_spot, self.land_candidates)
        self.assertEqual(self.land2, nearest_land)

    def test_find_nearest_land_a3(self):
        """ススムA3圃場の正面からの撮影で、正しく最寄りの圃場が特定できることをテストします。

        撮影位置をススムA3の正面に設定し、find_nearest_land関数が
        ススムA3を最も近い圃場として正しく特定できることを検証します。
        """
        photo_spot = CaptureLocation(
            XarvioCoord(longitude=137.64938, latitude=34.74374)
        )
        service = PhotoProcessingService()
        nearest_land = service.find_nearest_land(photo_spot, self.land_candidates)
        self.assertEqual(self.land3, nearest_land)

    def test_find_nearest_land_a4(self):
        """ススムA4圃場の正面からの撮影で、正しく最寄りの圃場が特定できることをテストします。

        撮影位置をススムA4の正面に設定し、find_nearest_land関数が
        ススムA4を最も近い圃場として正しく特定できることを検証します。
        """
        photo_spot = CaptureLocation(XarvioCoord(longitude=137.6496, latitude=34.7434))
        service = PhotoProcessingService()
        nearest_land = service.find_nearest_land(photo_spot, self.land_candidates)
        self.assertEqual(self.land4, nearest_land)

    def test_process_photos(self):
        """複数写真の処理をテスト - find_nearest_land メソッドをモック化"""
        # 写真のパスリスト（複数）
        photo_paths = [
            "path/to/photo1.jpg",
            "path/to/photo2.jpg",
            "path/to/photo3.jpg",
            "path/to/photo4.jpg",
        ]

        service = PhotoProcessingService()

        # find_nearest_landメソッドをモック化
        with patch.object(service, "find_nearest_land") as mock_find_nearest_land:
            # 写真ごとに異なる最寄りの土地を設定
            mock_find_nearest_land.side_effect = [
                self.land1,  # 1枚目の写真はススムA1に最も近い
                self.land2,  # 2枚目の写真はススムA2に最も近い
                self.land3,  # 3枚目の写真はススムA3に最も近い
                self.land4,  # 4枚目の写真はススムA4に最も近い
            ]

            # calculate_distanceメソッドもモック化して一定の距離を返す
            with patch.object(service, "calculate_distance", return_value=10.0):
                # 処理を実行
                result = service.process_photos(photo_paths, self.land_candidates)

                # 結果の検証
                self.assertEqual(4, len(result))
                self.assertEqual(
                    self.land1, result[0].nearest_land
                )  # 1枚目はA1に紐づく
                self.assertEqual(
                    self.land2, result[1].nearest_land
                )  # 2枚目はA2に紐づく
                self.assertEqual(
                    self.land3, result[2].nearest_land
                )  # 3枚目はA3に紐づく
                self.assertEqual(
                    self.land4, result[3].nearest_land
                )  # 4枚目はA4に紐づく

                # モックが正しく呼び出されたことを確認
                self.assertEqual(len(photo_paths), mock_find_nearest_land.call_count)
