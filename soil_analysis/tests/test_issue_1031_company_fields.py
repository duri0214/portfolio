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
        self.category = CompanyCategory.objects.create(name="生産者")
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

    def test_list_shows_empty_company_and_add_land_action(self):
        """
        シナリオ:
        - 入力: 圃場未登録の企業が1件ある。
        - 操作: 企業別圃場一覧を開く。
        - 結果: 企業詳細と最初の圃場を追加するリンクが表示される。
        """
        response = self.client.get(reverse("soil:company_land_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, reverse("soil:company_detail", kwargs={"pk": self.company.id})
        )
        self.assertContains(
            response,
            reverse("soil:land_create", kwargs={"company_id": self.company.id}),
        )
        self.assertContains(response, "圃場はまだ登録されていません")

    def test_list_shows_registered_land_and_company_detail_links(self):
        """
        シナリオ:
        - 入力: 企業に圃場が1件登録されている。
        - 操作: 企業別圃場一覧と企業詳細を開く。
        - 結果: どちらの画面からも圃場詳細へ移動できる。
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
