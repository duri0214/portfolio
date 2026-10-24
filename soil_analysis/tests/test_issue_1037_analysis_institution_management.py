from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from soil_analysis.forms import LandLedgerCreateForm
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


class AnalysisInstitutionManagementViewTests(TestCase):
    def setUp(self):
        self.farmer_category = CompanyCategory.objects.create(name="農業法人")
        self.institution_category = CompanyCategory.objects.create(name="分析機関")
        self.farmer = Company.objects.create(
            name="テスト農園", category=self.farmer_category
        )
        self.institution = Company.objects.create(
            name="川田研究所", category=self.institution_category
        )
        self.replacement = Company.objects.create(
            name="引き継ぎ分析センター", category=self.institution_category
        )
        self.user = get_user_model().objects.create_user(username="field-owner")
        area = JmaArea.objects.create(code="01", name="北海道")
        prefecture = JmaPrefecture.objects.create(
            code="0101", name="北海道", jma_area=area
        )
        region = JmaRegion.objects.create(
            code="010101", name="札幌", jma_prefecture=prefecture
        )
        city = JmaCity.objects.create(code="0101011", name="札幌市", jma_region=region)
        cultivation_type = CultivationType.objects.create(name="露地")
        self.land = Land.objects.create(
            name="第一圃場",
            company=self.farmer,
            jma_city=city,
            cultivation_type=cultivation_type,
            owner=self.user,
            center="43.0,141.0",
        )
        self.crop = Crop.objects.create(name="小麦")
        self.period = LandPeriod.objects.create(name="播種時", year=2026)
        self.sampling_method = SamplingMethod.objects.create(name="5点法", times=5)

    def _create_ledger(self):
        return LandLedger.objects.create(
            sampling_date=date(2026, 4, 1),
            analytical_agency=self.institution,
            crop=self.crop,
            land=self.land,
            land_period=self.period,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )

    def test_company_land_list_shows_only_farmers_including_empty_farmers(self):
        """
        シナリオ:
        - 入力: 圃場未登録の農業法人と分析機関が登録されている。
        - 操作: 企業別圃場一覧を開く。
        - 期待値: 農業法人だけが表示され、圃場追加導線を利用できる。
        """
        response = self.client.get(reverse("soil:company_land_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.farmer.name)
        self.assertNotContains(response, self.institution.name)
        self.assertContains(
            response,
            reverse("soil:land_create", kwargs={"company_id": self.farmer.id}),
        )

    def test_analysis_institution_can_be_created_and_edited(self):
        """
        シナリオ:
        - 入力: 分析機関カテゴリが登録されている。
        - 操作: 管理画面から分析機関を追加し、名称を編集する。
        - 期待値: 作成・編集後も分析機関カテゴリの会社として一覧に表示される。
        """
        create_response = self.client.post(
            reverse("soil:analysis_institution_create"),
            {"name": "新規分析室", "remark": "土壌化学分析"},
        )

        self.assertRedirects(create_response, reverse("soil:analysis_institution_list"))
        created = Company.objects.get(name="新規分析室")
        self.assertEqual(created.category, self.institution_category)

        update_response = self.client.post(
            reverse("soil:analysis_institution_update", kwargs={"pk": created.id}),
            {"name": "新規分析センター", "remark": "更新済み"},
        )

        self.assertRedirects(update_response, reverse("soil:analysis_institution_list"))
        created.refresh_from_db()
        self.assertEqual(created.name, "新規分析センター")
        self.assertContains(
            self.client.get(reverse("soil:analysis_institution_list")), created.name
        )

    def test_land_ledger_form_only_offers_analysis_institutions(self):
        """
        シナリオ:
        - 入力: 農業法人と複数の分析機関が登録されている。
        - 操作: 台帳作成フォームの分析機関選択肢を取得する。
        - 期待値: 分析機関だけを選択でき、農業法人は選択肢に含まれない。
        """
        form = LandLedgerCreateForm()

        self.assertSetEqual(
            set(form.fields["analytical_agency"].queryset.values_list("id", flat=True)),
            {self.institution.id, self.replacement.id},
        )

    def test_land_ledger_ajax_options_keep_analysis_institutions_available(self):
        """
        シナリオ:
        - 入力: 農業法人と複数の分析機関が登録されている。
        - 操作: 台帳作成モーダル用の選択肢を取得する。
        - 期待値: 化学分析の台帳で分析機関だけを選択できる。
        """
        response = self.client.get(reverse("soil:land_ledger_create_ajax"))

        self.assertEqual(response.status_code, 200)
        agency_ids = {agency["id"] for agency in response.json()["analytical_agencies"]}
        self.assertSetEqual(agency_ids, {self.institution.id, self.replacement.id})

    def test_delete_referenced_institution_transfers_ledger_before_deleting(self):
        """
        シナリオ:
        - 入力: 分析機関を参照する既存台帳と、引き継ぎ先の分析機関がある。
        - 操作: 削除画面で引き継ぎ先を指定して削除する。
        - 期待値: 台帳の参照先が引き継がれ、削除した分析機関は残らない。
        """
        ledger = self._create_ledger()
        delete_url = reverse(
            "soil:analysis_institution_delete", kwargs={"pk": self.institution.id}
        )

        get_response = self.client.get(delete_url)
        self.assertContains(get_response, "1 件の既存台帳")
        self.assertContains(get_response, "引き継ぎ先の分析機関")
        self.assertContains(get_response, self.replacement.name)
        self.assertNotContains(get_response, f"Company object ({self.replacement.id})")

        post_response = self.client.post(
            delete_url, {"replacement_agency": self.replacement.id}
        )

        self.assertRedirects(post_response, reverse("soil:analysis_institution_list"))
        self.assertFalse(Company.objects.filter(pk=self.institution.id).exists())
        ledger.refresh_from_db()
        self.assertEqual(ledger.analytical_agency, self.replacement)

    def test_delete_unused_institution_removes_it_without_a_replacement(self):
        """
        シナリオ:
        - 入力: 台帳から参照されていない分析機関がある。
        - 操作: 削除画面で削除する。
        - 期待値: 引き継ぎ先を指定しなくても分析機関を削除できる。
        """
        delete_url = reverse(
            "soil:analysis_institution_delete", kwargs={"pk": self.institution.id}
        )

        response = self.client.post(delete_url)

        self.assertRedirects(response, reverse("soil:analysis_institution_list"))
        self.assertFalse(Company.objects.filter(pk=self.institution.id).exists())
