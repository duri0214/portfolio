import os
from unittest import TestCase

from lib.geo.valueobject.coord import XarvioCoord
from soil_analysis.domain.valueobject.photo import AndroidPhoto
from soil_analysis.domain.valueobject.photo import IphonePhoto
from soil_analysis.domain.valueobject.photo_spot import PhotoSpot


class TestBasePhotoFunctionality(TestCase):
    """BasePhotoクラスとそのサブクラス（IphonePhoto、AndroidPhoto）の機能を統合的にテストするクラス。

    このテストクラスでは、写真クラス階層のコア機能（初期化、メタデータ抽出、位置情報処理など）を
    包括的にテストします。また、デバイス固有の機能（iPhoneの方位角など）についても検証します。
    """

    def setUp(self):
        """テスト環境のセットアップを行います。

        テストに必要なファイルパスの設定、テスト対象のインスタンス（IphonePhoto、AndroidPhoto）を
        作成します。各テストはこれらのインスタンスを使用して実行されます。
        """
        self.script_directory = os.path.dirname(os.path.abspath(__file__))

        # テスト用の写真ファイルパスの設定
        self.iphone_path = os.path.join(
            self.script_directory, "./iphone/IMG_1315_left.jpeg"
        )
        self.android_path = os.path.join(
            self.script_directory, "./android/JA中_all.jpg"
        )

        # テスト対象のインスタンス生成 (具象クラスを通じてBasePhotoの機能をテスト)
        self.iphone_photo = IphonePhoto(self.iphone_path)
        self.android_photo = AndroidPhoto(self.android_path)

    def test_photo_initialization(self):
        """写真オブジェクトの初期化プロセスをテストします。

        検証内容:
        1. ファイルパスが正しく設定されているか
        2. ファイル名が正しく抽出されているか
        3. 必須属性（exif_data, date, location）が初期化されているか

        このテストは、BasePhotoクラスのコンストラクタが正しく機能していることを確認し、
        そのサブクラスが適切に初期化されることを保証します。
        """
        # ファイルパスの設定が正しいことを確認
        self.assertEqual(self.iphone_path, self.iphone_photo.filepath)
        self.assertEqual("IMG_1315_left.jpeg", self.iphone_photo.filename)

        self.assertEqual(self.android_path, self.android_photo.filepath)
        self.assertEqual("JA中_all.jpg", self.android_photo.filename)

        # 必要な属性が初期化されていることを確認
        self.assertIsNotNone(self.iphone_photo.exif_data)
        self.assertIsNotNone(self.iphone_photo.date)
        self.assertIsNotNone(self.iphone_photo.location)

        self.assertIsNotNone(self.android_photo.exif_data)
        self.assertIsNotNone(self.android_photo.date)
        self.assertIsNotNone(self.android_photo.location)

    def test_extract_date(self):
        """写真メタデータからの日付抽出機能をテストします。

        検証内容:
        1. 正常系テスト：
           - IphonePhoto: "2023-07-05"の日付が正しく抽出されるか
           - AndroidPhoto: "2023-08-27"の日付が正しく抽出されるか

        2. 異常系テスト:
           - Image DateTimeがNoneの場合に適切なValueErrorが発生するか
           - テスト後に設定を元に戻し、他のテストへの影響がないことを保証

        このテストは、デバイスの種類に関わらず、メタデータから正確な日付情報を
        抽出できることを確認します。
        """
        # 正常系テスト
        self.assertEqual("2023-07-05", self.iphone_photo.date)
        self.assertEqual("2023-08-27", self.android_photo.date)

        # 異常系テスト - Exifデータなしの場合
        for photo in [self.iphone_photo, self.android_photo]:
            # 元の値を保存
            original_datetime = photo.exif_data.get("Image DateTime")

            # テスト実行
            photo.exif_data["Image DateTime"] = None
            with self.assertRaises(ValueError):
                photo._extract_date()

            # 状態を復元
            photo.exif_data["Image DateTime"] = original_datetime

    def test_extract_location(self):
        """写真のEXIFデータからの位置情報抽出機能をテストします。

        検証内容:
        1. 正常系テスト:
           - IphonePhoto: 経度140.41932067、緯度35.80548371が正しく抽出されるか
           - AndroidPhoto: 経度137.8266552、緯度34.6942567が正しく抽出されるか
           - 抽出された位置情報がPhotoSpotオブジェクトとして適切に生成されるか

        2. 異常系テスト:
           - GPS GPSLongitudeがNoneの場合に適切なValueErrorが発生するか
           - GPS GPSLatitudeがNoneの場合に適切なValueErrorが発生するか
           - テスト後に設定を元に戻し、他のテストへの影響がないことを保証

        このテストは、異なるデバイスで撮影された写真から、正確な位置情報を
        抽出・変換できることを確認します。また、必要なメタデータが欠けている場合の
        エラーハンドリングも検証します。
        """
        # iPhone位置情報の検証
        expected_iphone_loc = PhotoSpot(
            XarvioCoord(longitude=140.41932067, latitude=35.80548371)
        )
        self._assert_locations_equal(expected_iphone_loc, self.iphone_photo.location)

        # Android位置情報の検証
        expected_android_loc = PhotoSpot(
            XarvioCoord(longitude=137.8266552, latitude=34.6942567)
        )
        self._assert_locations_equal(expected_android_loc, self.android_photo.location)

        # 異常系テスト
        gps_fields = ["GPS GPSLongitude", "GPS GPSLatitude"]

        for photo in [self.iphone_photo, self.android_photo]:
            for field in gps_fields:
                # 元の値を保存
                original_value = photo.exif_data.get(field)

                # テスト実行
                photo.exif_data[field] = None
                with self.assertRaises(ValueError):
                    photo._extract_location()

                # 状態を復元
                photo.exif_data[field] = original_value

    def test_iphone_specific_features(self):
        """iPhoneクラス特有の機能をテストします。

        検証内容:
        1. 方位角抽出のテスト:
           - 期待される方位角値（195.21922317314022）が正しく抽出されるか
           - IphonePhotoオブジェクトの初期化時に方位角が自動的に計算されるか

        2. 方位角の異常系テスト:
           - GPS GPSImgDirectionがNoneの場合に適切なValueErrorが発生するか
           - テスト後に設定を元に戻し、他のテストへの影響がないことを保証

        このテストは、iPhoneデバイス特有の機能が正しく実装されていることを確認します。
        方位角はカメラの向きを示す重要な情報であり、特に測量や方向付けが必要な
        アプリケーションで重要です。
        """
        # 方位角抽出のテスト
        expected_azimuth = 195.21922317314022
        self.assertEqual(expected_azimuth, self.iphone_photo.azimuth)

        # 方位角の異常系テスト
        original_value = self.iphone_photo.exif_data.get("GPS GPSImgDirection")
        self.iphone_photo.exif_data["GPS GPSImgDirection"] = None

        with self.assertRaises(ValueError):
            self.iphone_photo._extract_azimuth()

        # 状態を復元
        self.iphone_photo.exif_data["GPS GPSImgDirection"] = original_value

    def _assert_locations_equal(self, expected, actual):
        """位置情報の比較を行うヘルパーメソッドです。

        PhotoSpotオブジェクトの比較を行い、経度と緯度が許容誤差（0.001度）内で
        一致しているかを確認します。浮動小数点の比較には直接的な等価比較ではなく、
        許容誤差を考慮した比較を使用します。

        Args:
            expected: 期待されるPhotoSpotオブジェクト
            actual: 実際のPhotoSpotオブジェクト

        該当テスト: test_extract_location
        """
        self.assertAlmostEqual(
            expected.adjusted_position.to_tuple()[0],
            actual.adjusted_position.to_tuple()[0],
            delta=0.001,
        )
        self.assertAlmostEqual(
            expected.adjusted_position.to_tuple()[1],
            actual.adjusted_position.to_tuple()[1],
            delta=0.001,
        )
