from types import SimpleNamespace
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from soil_analysis.models import (
    Company,
    CompanyCategory,
    CultivationType,
    JmaArea,
    JmaCity,
    JmaPrefecture,
    JmaRegion,
    Land,
)


class CompanyLandListViewTest(TestCase):
    def setUp(self):
        self.category = CompanyCategory.objects.create(name="農業法人")
        self.company = Company.objects.create(name="テスト農園", category=self.category)
        self.user = get_user_model().objects.create_user(username="field-owner")
        area = JmaArea.objects.create(code="01", name="北海道")
        prefecture = JmaPrefecture.objects.create(
            code="0101", name="北海道", jma_area=area
        )
        region = JmaRegion.objects.create(
            code="010101", name="札幌", jma_prefecture=prefecture
        )
        self.city = JmaCity.objects.create(
            code="0101011", name="札幌市", jma_region=region
        )
        self.cultivation_type = CultivationType.objects.create(name="露地")

    def _land(self, name="第一圃場"):
        return Land.objects.create(
            name=name,
            company=self.company,
            jma_city=self.city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="43.0,141.0",
        )

    def test_list_shows_empty_company_and_link_to_company_detail(self):
        """
        シナリオ:
        - 入力: 圃場未登録の企業が1件ある。
        - 操作: 企業別圃場一覧を開く。
        - 結果: 企業詳細へのリンクと、企業詳細から圃場を追加する案内が表示される。
        """
        response = self.client.get(reverse("soil:company_land_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, reverse("soil:company_detail", kwargs={"pk": self.company.id})
        )
        self.assertNotContains(
            response,
            reverse("soil:land_create", kwargs={"company_id": self.company.id}),
        )
        self.assertContains(response, "企業詳細から最初の圃場を登録してください")

    def test_list_shows_registered_land_and_company_detail_links(self):
        """
        シナリオ:
        - 入力: 企業に圃場が1件登録されている。
        - 操作: 企業別圃場一覧と企業詳細を開く。
        - 結果: どちらの画面からも圃場詳細へ移動でき、一覧では枠線付きの横並びリストを使わない。
        """
        land = self._land()

        list_response = self.client.get(reverse("soil:company_land_list"))
        detail_response = self.client.get(
            reverse("soil:company_detail", kwargs={"pk": self.company.id})
        )
        land_url = reverse(
            "soil:land_detail",
            kwargs={"company_id": self.company.id, "pk": land.id},
        )

        self.assertContains(list_response, land_url)
        self.assertContains(detail_response, land_url)
        self.assertContains(list_response, "row-cols-xl-5")
        self.assertNotContains(list_response, "list-group-horizontal-md")

    def test_list_and_detail_order_lands_by_prefecture_code(self):
        """
        シナリオ:
        - 入力: 北海道と沖縄県にそれぞれ圃場を登録する。
        - 操作: 企業別圃場一覧と会社詳細を開く。
        - 期待値: 両画面で圃場名の五十音順ではなく、北海道から沖縄県の順で表示されること。
        """
        hokkaido_land = self._land(name="北海道圃場")
        okinawa_area = JmaArea.objects.create(code="14", name="沖縄")
        okinawa_prefecture = JmaPrefecture.objects.create(
            code="471000", name="沖縄県", jma_area=okinawa_area
        )
        okinawa_region = JmaRegion.objects.create(
            code="471000", name="那覇", jma_prefecture=okinawa_prefecture
        )
        okinawa_city = JmaCity.objects.create(
            code="471000", name="那覇市", jma_region=okinawa_region
        )
        okinawa_land = Land.objects.create(
            name="あいう圃場",
            company=self.company,
            jma_city=okinawa_city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="26.2,127.7",
        )

        list_response = self.client.get(reverse("soil:company_land_list"))
        detail_response = self.client.get(
            reverse("soil:company_detail", kwargs={"pk": self.company.id})
        )
        list_lands = list_response.context["companies"][0].lands
        detail_lands = detail_response.context["company_lands"]

        self.assertEqual(
            [land.id for land in list_lands], [hokkaido_land.id, okinawa_land.id]
        )
        self.assertEqual(
            [land.id for land in detail_lands], [hokkaido_land.id, okinawa_land.id]
        )

    @patch("soil_analysis.views.PrefectureCommercialAreaService.build")
    def test_home_moves_company_and_import_actions_to_company_land_list(self, build):
        """
        シナリオ:
        - 入力: 地域分析ダッシュボードを表示できる状態である。
        - 操作: 土壌分析トップを開く。
        - 結果: 企業別圃場一覧へのリンクがあり、登録・取り込み操作への直リンクはない。
        """
        build.return_value = SimpleNamespace(
            area_count=47,
            land_count=0,
            active_area_count=0,
            risk_area_count=0,
            areas_by_weather_risk=[],
            areas=[],
            map_payload=[],
        )

        response = self.client.get(reverse("soil:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("soil:company_land_list"))
        self.assertNotContains(response, reverse("soil:company_create"))
        self.assertNotContains(response, reverse("soil:hardness_upload"))
        self.assertNotContains(response, reverse("soil:chemical_upload"))
