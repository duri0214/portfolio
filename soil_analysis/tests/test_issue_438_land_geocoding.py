from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
import requests

from lib.geo.valueobject.coord import GoogleMapsCoord
from soil_analysis.models import (
    Company,
    CompanyCategory,
    JmaArea,
    JmaCity,
    JmaPrefecture,
    JmaRegion,
)


class LandGeocodingViewTests(TestCase):
    def setUp(self):
        area = JmaArea.objects.create(code="01", name="北海道")
        self.prefecture = JmaPrefecture.objects.create(
            code="016000", name="石狩・空知・後志地方", jma_area=area
        )
        region = JmaRegion.objects.create(
            code="016000", name="石狩地方", jma_prefecture=self.prefecture
        )
        self.city = JmaCity.objects.create(
            code="0110000", name="札幌市", jma_region=region
        )

    @patch("soil_analysis.views.ForwardGeocoderService.get_coord_from_address")
    def test_address_geocoding_returns_first_yahoo_candidate_coordinate(
        self, get_coord
    ):
        """
        シナリオ:
        - 入力: 同じ系統に属する石狩地方と札幌市の選択値、Yahoo の代表座標。
        - 処理: 地域から中心座標への変換エンドポイントを POST する。
        - 期待値: Yahoo には北海道名と市区町村名を連結して渡し、緯度,経度を返すこと。
        """
        get_coord.return_value = GoogleMapsCoord(latitude=43.0618, longitude=141.3545)

        response = self.client.post(
            reverse("soil:land_geocode_address"),
            {"prefecture_id": self.prefecture.pk, "city_id": self.city.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["center"], "43.0618,141.3545")
        get_coord.assert_called_once_with("北海道札幌市")

    def test_address_geocoding_rejects_unselected_or_mismatched_administrative_areas(
        self,
    ):
        """
        シナリオ:
        - 入力: 都道府県または市区町村を選択していないリクエスト。
        - 処理: 地域から中心座標への変換エンドポイントを POST する。
        - 期待値: Yahoo API を呼ばず、選択を促すエラーを返すこと。
        """
        response = self.client.post(reverse("soil:land_geocode_address"), {})

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.json()["message"], "都道府県と市区町村を選択してください。"
        )

    @patch("soil_analysis.views.ForwardGeocoderService.get_coord_from_address")
    def test_address_geocoding_reports_yahoo_api_error(self, get_coord):
        """
        シナリオ:
        - 入力: 有効な地域選択と、通信に失敗する Yahoo API。
        - 処理: 地域から中心座標への変換エンドポイントを POST する。
        - 期待値: 既存入力の上書きを示す値を返さず、次の操作を判断できるエラーを返すこと。
        """
        get_coord.side_effect = requests.RequestException("network error")

        response = self.client.post(
            reverse("soil:land_geocode_address"),
            {"prefecture_id": self.prefecture.pk, "city_id": self.city.pk},
        )

        self.assertEqual(response.status_code, 502)
        self.assertNotIn("center", response.json())
        self.assertIn("座標候補を取得できませんでした", response.json()["message"])

    @patch("soil_analysis.views.ReverseGeocoderService.get_ydf_from_coord")
    def test_coordinate_geocoding_returns_matching_prefecture_and_city(self, get_ydf):
        """
        シナリオ:
        - 入力: 緯度,経度形式の中心座標と、北海道・札幌市を含む Yahoo 結果。
        - 処理: 中心座標から地域への変換エンドポイントを POST する。
        - 期待値: 対応する既存の都道府県と市区町村のIDを返すこと。
        """
        get_ydf.return_value = SimpleNamespace(
            feature=SimpleNamespace(
                prefecture=SimpleNamespace(name="北海道", code="01"),
                city=SimpleNamespace(name="札幌市"),
            )
        )

        response = self.client.post(
            reverse("soil:land_geocode_coordinate"), {"center": "43.0618, 141.3545"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["prefecture_id"], self.prefecture.pk)
        self.assertEqual(response.json()["city_id"], self.city.pk)
        get_ydf.assert_called_once()
        coordinate = get_ydf.call_args.args[0]
        self.assertEqual(coordinate.to_tuple(), (43.0618, 141.3545))

    def test_coordinate_geocoding_rejects_an_invalid_coordinate(self):
        """
        シナリオ:
        - 入力: 緯度,経度として解釈できない中心座標。
        - 処理: 中心座標から地域への変換エンドポイントを POST する。
        - 期待値: Yahoo API を呼ばず、中心座標欄に表示できる理由を返すこと。
        """
        response = self.client.post(
            reverse("soil:land_geocode_coordinate"), {"center": "札幌市"}
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["field"], "center")
        self.assertEqual(
            response.json()["message"],
            "中心座標は「緯度,経度」形式で入力してください。",
        )

    @patch("soil_analysis.views.ReverseGeocoderService.get_ydf_from_coord")
    def test_coordinate_geocoding_clears_unmatched_city(self, get_ydf):
        """
        シナリオ:
        - 入力: 北海道とマスタに存在しない市区町村を含む Yahoo 結果。
        - 処理: 中心座標から地域への変換エンドポイントを POST する。
        - 期待値: 都道府県は返し、市区町村は未選択として返すこと。
        """
        get_ydf.return_value = SimpleNamespace(
            feature=SimpleNamespace(
                prefecture=SimpleNamespace(name="北海道", code="01"),
                city=SimpleNamespace(name="未登録市"),
            )
        )

        response = self.client.post(
            reverse("soil:land_geocode_coordinate"), {"center": "43.0618,141.3545"}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["prefecture_id"], self.prefecture.pk)
        self.assertIsNone(response.json()["city_id"])
        self.assertIn("市区町村", response.json()["message"])

    def test_land_create_screen_displays_explicit_geocoding_actions_and_guidance(self):
        """
        シナリオ:
        - 入力: 圃場作成先の企業がある。
        - 処理: 圃場作成画面を開く。
        - 期待値: 双方向の変換ボタンと代表地点である旨の案内が表示されること。
        """
        category = CompanyCategory.objects.create(name="農業法人")
        company = Company.objects.create(name="テスト農園", category=category)

        response = self.client.get(
            reverse("soil:land_create", kwargs={"company_id": company.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "選択した地域から中心座標を設定")
        self.assertContains(response, "中心座標から地域を設定")
        self.assertContains(response, "圃場そのものの正確な位置ではありません")
        self.assertNotContains(response, 'value="35.658581,139.745433"')
        self.assertContains(
            response, 'class="d-flex justify-content-end mt-2"', count=2
        )
