from unittest import mock
from unittest.mock import patch

from django.test import TestCase

from lib.geo.valueobject.coord import GoogleMapsCoord
from lib.geo.yahoo_geocoder import ReverseGeocoderService, ForwardGeocoderService


class TestReverseGeocoderService(TestCase):
    """
    ReverseGeocoderService の逆ジオコーディング機能をテストする

    【テストシナリオ】
    Yahoo Geocoding APIを使って、緯度経度から住所情報を取得する機能をテストします。
    逆ジオコーディング（Reverse Geocoding）とは、地理座標（緯度・経度）から
    人間が読める住所（都道府県、市区町村、番地など）に変換する処理です。

    【主な用途】
    - 地図上でクリックした地点の住所を表示する
    - GPSで取得した位置情報から現在地の住所を取得する
    - 圃場や測定地点の座標から所在地を特定する
    """

    @patch("requests.get")
    def test_get_ydf_from_coord(self, mock_get):
        """
        【シナリオ】緯度経度から住所情報を取得する

        Given: 東京都港区赤坂の座標（緯度35.681236, 経度139.767125）
        When: Yahoo Geocoding APIで逆ジオコーディングを実行
        Then: 以下の住所情報が正しく取得できること
            - 都道府県: 東京都（とうきょうと）/ コード: 13
            - 市区町村: 港区（みなとく）/ コード: 13103
            - 詳細住所: 赤坂９丁目７
            - 完全住所: 東京都港区赤坂９丁目７－１
            - 国: 日本（JP）
            - 座標: point型（139.73134257366763,35.666049811559205）
        """
        mock_response = mock.Mock()
        mock_response.text = """
        <YDF xmlns="http://olp.yahooapis.jp/ydf/1.0" totalResultsReturned="1">
            <ResultInfo>
                <Count>1</Count>
                <Total>1</Total>
                <Start>1</Start>
                <Latency>0.18004202842712</Latency>
                <Status>200</Status>
                <Description>指定の地点の住所情報を取得する機能を提供します。</Description>
                <CompressType/>
            </ResultInfo>
            <Feature>
                <Property>
                    <Country>
                        <Code>JP</Code>
                        <Name>日本</Name>
                    </Country>
                    <Address>東京都港区赤坂９丁目７－１</Address>
                    <AddressElement>
                        <Name>東京都</Name>
                        <Kana>とうきょうと</Kana>
                        <Level>prefecture</Level>
                        <Code>13</Code>
                    </AddressElement>
                    <AddressElement>
                        <Name>港区</Name>
                        <Kana>みなとく</Kana>
                        <Level>city</Level>
                        <Code>13103</Code>
                    </AddressElement>
                    <AddressElement>
                        <Name>赤坂</Name>
                        <Kana>あかさか</Kana>
                        <Level>oaza</Level>
                    </AddressElement>
                    <AddressElement>
                        <Name>９丁目</Name>
                        <Kana>９ちょうめ</Kana>
                        <Level>aza</Level>
                    </AddressElement>
                    <AddressElement>
                        <Name>７</Name>
                        <Kana>７</Kana>
                        <Level>detail1</Level>
                    </AddressElement>
                    <Building>
                        <Id>B@iXzXO-G3A</Id>
                        <Name>ミッドタウン・タワー</Name>
                        <Floor>54</Floor>
                        <Area>5147</Area>
                    </Building>
                </Property>
                <Geometry>
                    <Type>point</Type>
                    <Coordinates>139.73134257366763,35.666049811559205</Coordinates>
                </Geometry>
            </Feature>
        </YDF>
        """
        mock_get.return_value = mock_response

        coord = GoogleMapsCoord(latitude=35.681236, longitude=139.767125)
        ydf = ReverseGeocoderService.get_ydf_from_coord(coord)

        assert ydf.result_info.count == 1
        assert ydf.result_info.total == 1
        assert ydf.result_info.start == 1
        assert abs(ydf.result_info.latency - 0.18004202842712) < 1e-6
        assert ydf.result_info.status == 200
        assert (
            ydf.result_info.description
            == "指定の地点の住所情報を取得する機能を提供します。"
        )

        assert ydf.feature.geometry.type == "point"
        assert (
            ydf.feature.geometry.coordinates == "139.73134257366763,35.666049811559205"
        )

        assert ydf.feature.country.code == "JP"
        assert ydf.feature.country.name == "日本"

        assert ydf.feature.address_full == "東京都港区赤坂９丁目７－１"

        assert ydf.feature.prefecture.name == "東京都"
        assert ydf.feature.prefecture.kana == "とうきょうと"
        assert ydf.feature.prefecture.level == "prefecture"
        assert ydf.feature.prefecture.code == "13"

        assert ydf.feature.city.name == "港区"
        assert ydf.feature.city.kana == "みなとく"
        assert ydf.feature.city.level == "city"
        assert ydf.feature.city.code == "13103"

        assert ydf.feature.detail.name == "赤坂９丁目７"
        assert ydf.feature.detail.kana == "あかさか９ちょうめ７"
        assert ydf.feature.detail.level == "detail"


class TestForwardGeocoderService(TestCase):
    """
    Yahoo Geocoding API を使って住所から緯度経度を取得するテスト
    """

    @patch("requests.get")
    def test_get_coord_from_address(self, mock_get):
        """
        【シナリオ】
        Given: "東京都港区赤坂9-7-1" という住所
        When: Yahoo Geocoding APIでジオコーディングを実行
        Then: 緯度35.666前後、経度139.731前後の座標が取得できること
        """
        xml_response = """
        <YDF xmlns="http://olp.yahooapis.jp/ydf/1.0">
            <ResultInfo>
                <Count>1</Count>
                <Total>1</Total>
                <Start>1</Start>
                <Status>200</Status>
                <Description>住所から緯度経度を検索する機能を提供します。</Description>
                <Latency>0.020</Latency>
            </ResultInfo>
            <Feature>
                <Id>1</Id>
                <Name>東京都港区赤坂9-7-1</Name>
                <Geometry>
                    <Type>point</Type>
                    <Coordinates>139.731342,35.666049</Coordinates>
                </Geometry>
                <Property>
                    <Address>東京都港区赤坂９丁目７－１</Address>
                    <AddressElement>
                        <Name>東京都</Name>
                        <Kana>とうきょうと</Kana>
                        <Level>prefecture</Level>
                        <Code>13</Code>
                    </AddressElement>
                    <AddressElement>
                        <Name>港区</Name>
                        <Kana>みなとく</Kana>
                        <Level>city</Level>
                        <Code>13103</Code>
                    </AddressElement>
                </Property>
            </Feature>
        </YDF>
        """
        mock_response = mock.Mock()
        mock_response.text = xml_response
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        coord = ForwardGeocoderService.get_coord_from_address("東京都港区赤坂9-7-1")

        self.assertAlmostEqual(coord.latitude, 35.666049, places=3)
        self.assertAlmostEqual(coord.longitude, 139.731342, places=3)

    @patch("requests.get")
    def test_get_coord_from_city_level_address(self, mock_get):
        """
        【シナリオ】
        Given: 「東京都港区」という市区町村レベルの住所文字列
        When: Yahoo Geocoding API でジオコーディングを実行
        Then: 港区の代表点（行政区の中心付近）の座標が返ること

        【補足】
        - 「東京都港区」などの地名レベルの入力に対しては、
          実際の建物や地形の中心ではなく、
          行政区画の代表座標（港区役所付近など）が返される。
        - Yahoo Geocoding API の仕様上、この代表座標は
          地形的な重心ではなく行政的な代表点。
        """
        xml_response = """
        <YDF xmlns="http://olp.yahooapis.jp/ydf/1.0">
            <ResultInfo>
                <Count>1</Count>
                <Total>1</Total>
                <Start>1</Start>
                <Status>200</Status>
                <Description>住所から緯度経度を検索する機能を提供します。</Description>
                <Latency>0.010</Latency>
            </ResultInfo>
            <Feature>
                <Id>1</Id>
                <Name>東京都港区</Name>
                <Geometry>
                    <Type>point</Type>
                    <Coordinates>139.751599,35.643956</Coordinates>
                </Geometry>
                <Property>
                    <Address>東京都港区</Address>
                </Property>
            </Feature>
        </YDF>
        """
        mock_response = mock.Mock()
        mock_response.text = xml_response
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        coord = ForwardGeocoderService.get_coord_from_address("東京都港区")

        # 港区の代表点（港区役所付近）の座標に近いことを確認
        self.assertAlmostEqual(coord.latitude, 35.6439, places=3)
        self.assertAlmostEqual(coord.longitude, 139.7515, places=3)

    @patch("requests.get")
    def test_multiple_candidates_uses_first_feature(self, mock_get):
        """
        複数候補が返った場合、最初のFeatureを使用する
        """
        xml_response = """
        <YDF xmlns="http://olp.yahooapis.jp/ydf/1.0">
            <ResultInfo>
                <Count>10</Count>
                <Total>2</Total>
                <Start>1</Start>
                <Status>200</Status>
                <Description>住所から緯度経度を検索する機能を提供します。</Description>
                <Latency>0.012</Latency>
            </ResultInfo>
            <Feature>
                <Id>1</Id>
                <Name>候補1</Name>
                <Geometry>
                    <Type>point</Type>
                    <Coordinates>139.7000,35.6000</Coordinates>
                </Geometry>
            </Feature>
            <Feature>
                <Id>2</Id>
                <Name>候補2</Name>
                <Geometry>
                    <Type>point</Type>
                    <Coordinates>140.0000,36.0000</Coordinates>
                </Geometry>
            </Feature>
        </YDF>
        """
        mock_response = mock.Mock()
        mock_response.text = xml_response
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        coord = ForwardGeocoderService.get_coord_from_address("曖昧な住所")

        self.assertAlmostEqual(coord.latitude, 35.6000, places=4)
        self.assertAlmostEqual(coord.longitude, 139.7000, places=4)

    @patch("requests.get")
    def test_no_results_raises_value_error(self, mock_get):
        """
        Total=0 の場合は ValueError("No results found") を送出する
        """
        xml_response = """
        <YDF xmlns="http://olp.yahooapis.jp/ydf/1.0">
            <ResultInfo>
                <Count>0</Count>
                <Total>0</Total>
                <Start>1</Start>
                <Status>200</Status>
                <Description>住所から緯度経度を検索する機能を提供します。</Description>
                <Latency>0.005</Latency>
            </ResultInfo>
        </YDF>
        """
        mock_response = mock.Mock()
        mock_response.text = xml_response
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        with self.assertRaises(ValueError) as ctx:
            ForwardGeocoderService.get_coord_from_address("存在しない住所")
        self.assertEqual(str(ctx.exception), "No results found")
