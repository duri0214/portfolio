from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from soil_analysis.models import (
    Company,
    CompanyCategory,
    Crop,
    CultivationType,
    JmaArea,
    JmaCity,
    JmaPrefecture,
    JmaRegion,
    Land,
    LandLedger,
    LandPeriod,
    SamplingMethod,
)


class LandDeletionViewTests(TestCase):
    def setUp(self):
        self.farmer_category = CompanyCategory.objects.create(name="農業法人")
        self.institution_category = CompanyCategory.objects.create(name="分析機関")
        self.company = Company.objects.create(
            name="削除対象の農業法人", category=self.farmer_category
        )
        self.other_company = Company.objects.create(
            name="別の農業法人", category=self.farmer_category
        )
        self.institution = Company.objects.create(
            name="分析機関", category=self.institution_category
        )
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
        self.cultivation_type = CultivationType.objects.create(name="畑")
        self.crop = Crop.objects.create(name="水稲")
        self.period = LandPeriod.objects.create(name="春", year=2026)
        self.sampling_method = SamplingMethod.objects.create(name="5点法", times=5)

    def _create_land(self, *, company=None, name="削除対象の圃場"):
        return Land.objects.create(
            name=name,
            company=company or self.company,
            jma_city=self.city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="43.0,141.0",
        )

    def _create_ledger(self, land):
        return LandLedger.objects.create(
            sampling_date=date(2026, 4, 1),
            analytical_agency=self.institution,
            crop=self.crop,
            land=land,
            land_period=self.period,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )

    def delete_url(self, land=None, company=None):
        land = land or self.land
        company = company or land.company
        return reverse(
            "soil:land_delete",
            kwargs={"company_id": company.id, "pk": land.id},
        )

    def detail_url(self, land=None, company=None):
        land = land or self.land
        company = company or land.company
        return reverse(
            "soil:land_detail",
            kwargs={"company_id": company.id, "pk": land.id},
        )

    def test_company_detail_has_delete_action_for_each_land(self):
        """
        シナリオ:
        - 入力: 農業法人詳細画面に圃場が表示されている。
        - 処理: 所属圃場の削除導線を確認する。
        - 期待値: 各圃場の削除確認画面へのリンクが表示されること。
        """
        self.land = self._create_land()

        response = self.client.get(
            reverse("soil:company_detail", kwargs={"pk": self.company.id})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.delete_url())
        self.assertContains(response, "圃場を削除")

    def test_land_without_ledger_is_deleted_after_confirmation(self):
        """
        シナリオ:
        - 入力: 台帳のない圃場と、同じ法人に属する別の圃場がある。
        - 処理: 削除確認画面で確認せず送信した後、確認して削除する。
        - 期待値: 確認なしでは削除されず、確認後は対象圃場だけが削除されて法人詳細へ戻ること。
        """
        self.land = self._create_land()
        other_land = self._create_land(name="残す圃場")
        delete_url = self.delete_url()

        get_response = self.client.get(delete_url)
        self.assertContains(get_response, "関連する台帳はありません")

        unconfirmed_response = self.client.post(delete_url)
        self.assertEqual(unconfirmed_response.status_code, 200)
        self.assertTrue(Land.objects.filter(pk=self.land.id).exists())

        response = self.client.post(delete_url, {"confirm_deletion": "on"})

        self.assertRedirects(
            response,
            reverse("soil:company_detail", kwargs={"pk": self.company.id}),
        )
        self.assertFalse(Land.objects.filter(pk=self.land.id).exists())
        self.assertTrue(Company.objects.filter(pk=self.company.id).exists())
        self.assertTrue(Land.objects.filter(pk=other_land.id).exists())

    def test_land_with_ledger_is_not_deleted(self):
        """
        シナリオ:
        - 入力: 台帳が紐づく圃場がある。
        - 処理: 削除確認画面を開き、削除を送信する。
        - 期待値: 台帳件数と削除できない理由が表示され、圃場と台帳が残ること。
        """
        self.land = self._create_land()
        ledger = self._create_ledger(self.land)
        delete_url = self.delete_url()

        get_response = self.client.get(delete_url)
        self.assertContains(get_response, "関連する台帳: 1 件")
        self.assertContains(get_response, "この圃場は削除できません")
        self.assertContains(get_response, "台帳を整理してから")

        post_response = self.client.post(delete_url, {"confirm_deletion": "on"})

        self.assertEqual(post_response.status_code, 200)
        self.assertContains(post_response, "この圃場は削除できません")
        self.assertTrue(Land.objects.filter(pk=self.land.id).exists())
        self.assertTrue(LandLedger.objects.filter(pk=ledger.id).exists())

    def test_land_delete_route_requires_matching_company(self):
        """
        シナリオ:
        - 入力: 別法人の ID を指定した圃場削除 URL がある。
        - 処理: 圃場削除 URL を開く。
        - 期待値: 対象圃場が見つからず削除確認画面を表示しないこと。
        """
        self.land = self._create_land()

        response = self.client.get(self.delete_url(company=self.other_company))

        self.assertEqual(response.status_code, 404)
        self.assertTrue(Land.objects.filter(pk=self.land.id).exists())
