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


class CompanyDeletionViewTests(TestCase):
    def setUp(self):
        self.farmer_category = CompanyCategory.objects.create(name="農業法人")
        self.institution_category = CompanyCategory.objects.create(name="分析機関")
        self.company = Company.objects.create(
            name="削除対象の農業法人", category=self.farmer_category
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

    def _create_land(self):
        return Land.objects.create(
            name="削除対象の圃場",
            company=self.company,
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

    def test_unused_company_is_deleted_after_confirmation(self):
        """
        シナリオ:
        - 入力: 圃場も台帳も持たない農業法人がある。
        - 操作: 削除確認画面で確認チェックを入れて削除する。
        - 期待値: 農業法人だけが削除され、企業別圃場一覧へ戻る。
        """
        delete_url = reverse("soil:company_delete", kwargs={"pk": self.company.id})

        response = self.client.get(delete_url)
        self.assertContains(response, self.company.name)
        self.assertContains(response, "関連する圃場・台帳はありません")

        response = self.client.post(delete_url)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(Company.objects.filter(pk=self.company.id).exists())

        response = self.client.post(delete_url, {"confirm_deletion": "on"})

        self.assertRedirects(response, reverse("soil:company_land_list"))
        self.assertFalse(Company.objects.filter(pk=self.company.id).exists())

    def test_company_list_identifies_delete_action_as_company_deletion(self):
        """
        シナリオ:
        - 入力: 圃場未登録の農業法人が企業別圃場一覧に表示されている。
        - 操作: 一覧の企業名付近にある削除アイコンを確認する。
        - 期待値: 削除対象が企業であることがラベルから分かる。
        """
        response = self.client.get(reverse("soil:company_land_list"))

        self.assertContains(
            response,
            f'aria-label="{self.company.name}を削除"',
        )
        self.assertContains(response, f"{self.company.name}を削除")

    def test_company_with_land_and_ledger_is_not_deleted(self):
        """
        シナリオ:
        - 入力: 農業法人に圃場と、その圃場の台帳が登録されている。
        - 操作: 削除確認画面を開き、削除を送信する。
        - 期待値: 関連件数と整理操作が表示され、法人・圃場・台帳は残る。
        """
        land = self._create_land()
        ledger = self._create_ledger(land)
        delete_url = reverse("soil:company_delete", kwargs={"pk": self.company.id})

        get_response = self.client.get(delete_url)
        self.assertContains(get_response, "関連する圃場: 1 件")
        self.assertContains(get_response, "関連する台帳: 1 件")
        self.assertContains(get_response, "圃場と台帳を整理してから")

        post_response = self.client.post(delete_url, {"confirm_deletion": "on"})

        self.assertEqual(post_response.status_code, 200)
        self.assertContains(post_response, "この農業法人は削除できません")
        self.assertTrue(Company.objects.filter(pk=self.company.id).exists())
        self.assertTrue(Land.objects.filter(pk=land.id).exists())
        self.assertTrue(LandLedger.objects.filter(pk=ledger.id).exists())

    def test_analysis_institution_cannot_use_company_deletion_route(self):
        """
        シナリオ:
        - 入力: 分析機関が登録されている。
        - 操作: 農業法人削除のURLへアクセスする。
        - 期待値: 分析機関は対象外となり、農業法人用の削除操作はできない。
        """
        response = self.client.get(
            reverse("soil:company_delete", kwargs={"pk": self.institution.id})
        )

        self.assertEqual(response.status_code, 404)
        self.assertNotContains(
            self.client.get(reverse("soil:analysis_institution_list")),
            reverse("soil:company_delete", kwargs={"pk": self.company.id}),
        )
        self.assertNotContains(
            self.client.get(
                reverse("soil:company_detail", kwargs={"pk": self.institution.id})
            ),
            reverse("soil:company_delete", kwargs={"pk": self.institution.id}),
        )
