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
        """テストの前提条件とテストデータを設定します。

        テストデータとして「ススムA1」〜「ススムA4」という4つの圃場と、
        それぞれの圃場の正面から撮影したと想定される座標を使用しています。

        圃場データ:
        - ススムA1: (139.6, 35.7) 付近に位置する圃場
        - ススムA2: (139.7, 35.7) 付近に位置する圃場
        - ススムA3: (139.6, 35.6) 付近に位置する圃場
        - ススムA4: (139.7, 35.6) 付近に位置する圃場

        写真データ:
        - 各圃場の代表的な位置から撮影したと仮定
        - カメラの方向情報を含む位置データを使用
        - AndroidPhotoクラスをモック化して撮影位置を制御

        Notes:
        - 実際の写真ファイルは使用せず、モックオブジェクトで代用
        - 座標はテスト用の仮想的な値であり、実際の地理情報とは異なる
        - 圃場間の距離は十分に離れており、最寄り判定が明確になるよう設計
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
        """process_photosメソッドのテスト：複数写真の処理と最寄り圃場の関連付け機能

        このテストでは、様々な位置情報を持つ複数の写真ファイルを処理し、
        各写真に最も近い圃場を正確に関連付けられるかを検証します。

        検証内容:
        1. 複数の写真（4枚）を正しく処理できること
        2. 各写真に対して、実際の座標計算に基づいて最寄りの圃場を特定できること
        3. 全ての写真が期待通りの圃場と関連付けられること（A1～A4）

        テストアプローチ:
        - 各写真パスに対応する特定の座標を設定（圃場A1～A4にそれぞれ最も近くなる座標）
        - AndroidPhotoクラスのモックは、写真ファイルパスに応じて異なる座標情報を返すように設定
        - 実際のfind_nearest_landメソッドとcalculate_distanceメソッドを使用して
          座標ベースの距離計算と最寄り圃場の特定を検証

        データ設定:
        - 写真1: ススムA1圃場に最も近い座標（経度:137.6487867, 緯度:34.7441225）
        - 写真2: ススムA2圃場に最も近い座標（経度:137.648955, 緯度:34.7438825）
        - 写真3: ススムA3圃場に最も近い座標（経度:137.6491916, 緯度:34.7436416）
        - 写真4: ススムA4圃場に最も近い座標（経度:137.6505066, 緯度:34.7433425）

        期待結果:
        - 写真1がススムA1圃場と関連付けられること
        - 写真2がススムA2圃場と関連付けられること
        - 写真3がススムA3圃場と関連付けられること
        - 写真4がススムA4圃場と関連付けられること
        """
        # 各写真パスと対応する座標をマッピング
        photo_location_map = {
            "path/to/photo1.jpg": XarvioCoord(longitude=137.64905, latitude=34.74424),
            "path/to/photo2.jpg": XarvioCoord(longitude=137.64921, latitude=34.744),
            "path/to/photo3.jpg": XarvioCoord(longitude=137.64938, latitude=34.74374),
            "path/to/photo4.jpg": XarvioCoord(longitude=137.6496, latitude=34.7434),
        }

        # AndroidPhotoのモックが毎回異なる座標を返すように設定
        def android_photo_side_effect(file_path):
            mock = MagicMock()
            location_mock = MagicMock()
            location_mock.adjusted_position = photo_location_map[file_path]
            mock.location = location_mock
            return mock

        # モックの設定
        self.mock_android_photo.side_effect = android_photo_side_effect

        # テスト実行
        service = PhotoProcessingService()
        result = service.process_photos(
            list(photo_location_map.keys()), self.land_candidates
        )

        # 検証
        self.assertEqual(self.land1, result[0].nearest_land)
        self.assertEqual(self.land2, result[1].nearest_land)
        self.assertEqual(self.land3, result[2].nearest_land)
        self.assertEqual(self.land4, result[3].nearest_land)

        # デバッグ出力（Googleマップで確認できる形式）
        for i, r in enumerate(result):
            photo_path = list(photo_location_map.keys())[i]
            nearest_land = r.nearest_land
            print(f"結果 {i + 1}: ファイル={photo_path}, 圃場={nearest_land.name}")

            # 写真の座標をGoogleマップ形式で出力
            photo_coord = photo_location_map[photo_path]
            print(f"  写真の座標: {photo_coord.to_google().to_str()}")

            # 最寄り圃場の座標をGoogleマップ形式で出力
            land_coord = nearest_land.center
            print(f"  圃場の座標: {land_coord.to_google().to_str()}")

            # 距離も表示 - 更新された引数名でメソッドを呼び出す
            print(
                f"  距離: {service.calculate_distance(photo_spot=photo_coord, land_spot=nearest_land, unit='m'):.2f}m"
            )
