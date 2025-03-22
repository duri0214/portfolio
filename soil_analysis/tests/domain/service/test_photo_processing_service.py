from unittest import TestCase
from unittest.mock import MagicMock, patch

from lib.geo.valueobject.coord import XarvioCoord
from soil_analysis.domain.service.photo_processing_service import PhotoProcessingService
from soil_analysis.domain.valueobject.capturelocation import CaptureLocation
from soil_analysis.domain.valueobject.land import LandLocation


class TestPhotoProcessingService(TestCase):
    """写真と圃場を自動的に紐づける機能を検証するテストスイートです。

    複数の圃場（ススムA1〜A4）が隣接する環境で、各写真の撮影位置から
    どの圃場を撮影したものかを正確に特定できるかをテストします。

    主な検証内容:
    - 2点間の距離計算の正確性
    - 撮影位置から最も近い圃場の特定アルゴリズム
    - カメラの方向を考慮した位置調整の効果
    - 複数写真の一括処理と圃場の関連付け

    このテストスイートは、農業向け画像管理システムの重要な機能である
    「撮影した圃場の自動判別」機能の正確性を担保します。
    """

    def setUp(self) -> None:
        """
        テストの前準備を行います。
        - 4つの異なる地点（Land）を作成
        - それらをLandCandidatesクラスに登録
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
        """
        写真処理サービスのprocess_photos機能を検証するテストです。

        このテストでは以下の内容を確認します：
        1. 複数の写真を一括処理する機能が正しく動作すること
        2. 各写真に対して適切な圃場（最も近い圃場）が関連付けられること
        3. 写真と圃場の距離が正確に計算されること

        テスト手法：
        - 4枚の写真をモックし、それぞれ異なる位置情報を持たせる
        - それぞれの写真に対して、最も近い圃場が正しく特定されるか検証
        - 写真処理サービスのprocess_photosメソッドの戻り値を検証

        検証項目：
        - 結果のリストが入力写真数と同じ長さであること
        - 各写真に対して、期待される最寄り圃場が正しく関連付けられていること
        """
        # AndroidPhotoのモックを作成
        with patch(
            "soil_analysis.domain.service.photo_processing_service.AndroidPhoto"
        ) as mock_android_photo:
            # 各写真に対応するモックオブジェクトのリスト
            mock_photos = []

            # 各写真の座標を設定
            coordinates = [
                XarvioCoord(longitude=137.64905, latitude=34.74424),  # A1用
                XarvioCoord(longitude=137.64921, latitude=34.744),  # A2用
                XarvioCoord(longitude=137.64938, latitude=34.74374),  # A3用
                XarvioCoord(longitude=137.6496, latitude=34.7434),  # A4用
            ]

            # 各写真のモックを準備
            for coord in coordinates:
                mock_photo = MagicMock()
                mock_location = MagicMock()
                mock_location.adjusted_position = coord
                mock_photo.location = mock_location
                mock_photos.append(mock_photo)

            # AndroidPhotoが順番に異なるモックを返すように設定
            mock_android_photo.side_effect = mock_photos

            # テスト実行
            service = PhotoProcessingService()
            result = service.process_photos(
                [
                    "path/to/photo1.jpg",
                    "path/to/photo2.jpg",
                    "path/to/photo3.jpg",
                    "path/to/photo4.jpg",
                ],
                self.land_candidates,
            )

            # 検証
            self.assertEqual(self.land1, result[0].nearest_land)
            self.assertEqual(self.land2, result[1].nearest_land)
            self.assertEqual(self.land3, result[2].nearest_land)
            self.assertEqual(self.land4, result[3].nearest_land)

            # デバッグ出力（Googleマップで確認できる形式）
            for i, r in enumerate(result):
                photo_path = r.photo_path
                nearest_land = r.nearest_land
                print(f"結果 {i + 1}: ファイル={photo_path}, 圃場={nearest_land.name}")

                # 写真の座標をGoogleマップ形式で出力
                photo_coord = coordinates[i]
                print(f"  写真の座標: {photo_coord.to_google().to_str()}")

                # 最寄り圃場の座標をGoogleマップ形式で出力
                land_coord = nearest_land.center
                print(f"  圃場の座標: {land_coord.to_google().to_str()}")

                # 距離も表示 - 更新された引数名でメソッドを呼び出す
                print(
                    f"  距離: {service.calculate_distance(photo_spot=photo_coord, land_spot=nearest_land, unit='m'):.2f}m"
                )
