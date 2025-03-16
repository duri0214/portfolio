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
        """複数写真の処理と圃場紐づけ機能をテストします。

        実際のAndroid写真ファイルを使用して、process_photos関数が
        写真のGPSメタデータを抽出し、適切な圃場と紐づけられることを検証します。

        このテストでは：
        1. 複数の写真ファイルのパスをリストとして渡す
        2. 各写真から位置情報を抽出
        3. 各写真に対して最も近い圃場を特定
        4. 写真と圃場の紐づけ情報が正しく返されることを確認
        """
        # AndroidPhotoクラスのモック
        with patch(
            "soil_analysis.domain.valueobject.photo.androidphoto.AndroidPhoto"
        ) as mock_android_photo:
            # 1枚目の写真のモック設定
            mock_instance1 = MagicMock()
            mock_instance1.location = CaptureLocation(
                longitude=139.456, latitude=35.123, azimuth=90  # 東向き
            )

            # 2枚目の写真のモック設定
            mock_instance2 = MagicMock()
            mock_instance2.location = CaptureLocation(
                longitude=139.457, latitude=35.124, azimuth=180  # 南向き
            )

            # サイド・エフェクト設定で連続する呼び出しに対して異なる値を返す
            mock_android_photo.side_effect = [mock_instance1, mock_instance2]

            # テスト対象のメソッド実行
            service = PhotoProcessingService()
            result = service.process_photos(self.photo_paths, self.land_candidates)

            # 結果の検証
            self.assertEqual(len(result), 2)  # 2つの写真が処理されたことを確認

            # 各PhotoLandAssociationオブジェクトの検証
            self.assertIsInstance(result[0], PhotoLandAssociation)
            self.assertIsInstance(result[1], PhotoLandAssociation)

            # 写真パスの検証
            self.assertEqual(result[0].photo_path, self.photo_paths[0])
            self.assertEqual(result[1].photo_path, self.photo_paths[1])

            # 圃場の紐づけ検証（位置情報から期待される圃場）
            # mock_instance1の位置情報に基づいて期待される圃場
            self.assertEqual(
                result[0].nearest_land, self.land1
            )  # 例：最も近いのがland1と想定

            # mock_instance2の位置情報に基づいて期待される圃場
            self.assertEqual(
                result[1].nearest_land, self.land2
            )  # 例：最も近いのがland2と想定

            # 距離情報が設定されていることを確認
            self.assertIsNotNone(result[0].distance)
            self.assertIsNotNone(result[1].distance)
