from unittest import mock
from unittest.mock import patch

from django.test import TestCase

from soil_analysis.domain.service.geocode.yahoo import ReverseGeocoderService
from soil_analysis.domain.valueobject.coords.googlemapcoords import GoogleMapCoords


class TestGetYdfFromCoords(TestCase):
    @patch("requests.get")
    def test_get_ydf_from_coords(self, mock_get):
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

        coords = GoogleMapCoords(latitude=35.681236, longitude=139.767125)
        ydf = ReverseGeocoderService.get_ydf_from_coords(coords)

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
