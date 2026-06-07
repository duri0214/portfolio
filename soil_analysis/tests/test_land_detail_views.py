from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from soil_analysis.models import (
    Company,
    CompanyCategory,
    Crop,
    CultivationType,
    Device,
    JmaArea,
    JmaCity,
    JmaPrefecture,
    JmaRegion,
    Land,
    LandBlock,
    LandLedger,
    LandPeriod,
    SamplingMethod,
    SoilChemicalMeasurement,
    SoilHardnessMeasurement,
)


class LandDetailViewTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="testuser")

        category = CompanyCategory.objects.create(name="テストカテゴリ")
        self.company = Company.objects.create(name="テスト法人", category=category)

        area = JmaArea.objects.create(code="01", name="テストエリア")
        pref = JmaPrefecture.objects.create(code="0101", name="テスト県", jma_area=area)
        region = JmaRegion.objects.create(
            code="010101", name="テスト地域", jma_prefecture=pref
        )
        city = JmaCity.objects.create(
            code="0101011", name="テスト市", jma_region=region
        )

        self.cultivation_type = CultivationType.objects.create(name="露地")
        self.crop = Crop.objects.create(name="キャベツ")
        self.sampling_method = SamplingMethod.objects.create(name="5点法", times=5)
        self.land = Land.objects.create(
            name="FIELD001",
            company=self.company,
            jma_city=city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="36.0,140.0",
        )

    def create_ledger(self, *, period_name, year, sampling_date):
        period = LandPeriod.objects.create(name=period_name, year=year)
        return LandLedger.objects.create(
            land=self.land,
            land_period=period,
            sampling_date=sampling_date,
            analytical_agency=self.company,
            crop=self.crop,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )

    def detail_url(self):
        return reverse(
            "soil:land_detail",
            kwargs={"company_id": self.company.id, "pk": self.land.id},
        )

    def report_url(self, ledger):
        return reverse(
            "soil:standard_report",
            kwargs={"company_id": self.company.id, "land_ledger_id": ledger.id},
        )

    def test_land_detail_orders_ledgers_by_year_ascending(self):
        """
        シナリオ:
        - 入力: 2027年、2026年の順に作成された通知表台帳。
        - 処理: 圃場詳細画面を表示する。
        - 期待値: 通知表台帳が年度昇順で 2026年、2027年の順に表示されること。
        """
        self.create_ledger(
            period_name="播種時", year=2027, sampling_date=date(2027, 3, 3)
        )
        self.create_ledger(
            period_name="播種時", year=2026, sampling_date=date(2026, 3, 3)
        )

        response = self.client.get(self.detail_url())

        self.assertEqual(response.status_code, 200)
        ledgers = response.context["object"].ledgers
        self.assertEqual([ledger.land_period.year for ledger in ledgers], [2026, 2027])

    def test_land_detail_disables_report_button_without_measurements(self):
        """
        シナリオ:
        - 入力: 化学データも硬度データも紐づいていない通知表台帳。
        - 処理: 圃場詳細画面を表示する。
        - 期待値: 通知表表示のリンクは出ず、disabled の操作ボタンが表示されること。
        """
        ledger = self.create_ledger(
            period_name="播種時", year=2026, sampling_date=date(2026, 3, 3)
        )

        response = self.client.get(self.detail_url())

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'href="{self.report_url(ledger)}"')
        self.assertContains(
            response, "化学データまたは硬度データが登録されると表示できます"
        )
        self.assertContains(response, "disabled")

    def test_land_detail_enables_report_button_with_chemical_measurement(self):
        """
        シナリオ:
        - 入力: 化学データが紐づいた通知表台帳。
        - 処理: 圃場詳細画面を表示する。
        - 期待値: 通知表表示リンクが有効な操作として表示されること。
        """
        ledger = self.create_ledger(
            period_name="播種時", year=2026, sampling_date=date(2026, 3, 3)
        )
        SoilChemicalMeasurement.objects.create(land_ledger=ledger, ph=6.5, ec=0.1)

        response = self.client.get(self.detail_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{self.report_url(ledger)}"')

    def test_land_detail_enables_report_button_with_hardness_measurement(self):
        """
        シナリオ:
        - 入力: 硬度データだけが紐づいた通知表台帳。
        - 処理: 圃場詳細画面を表示する。
        - 期待値: 化学データがなくても通知表表示リンクが有効な操作として表示されること。
        """
        ledger = self.create_ledger(
            period_name="播種時", year=2026, sampling_date=date(2026, 3, 3)
        )
        device = Device.objects.create(name="硬度計")
        block = LandBlock.objects.create(name="A1")
        SoilHardnessMeasurement.objects.create(
            set_memory=1,
            set_datetime=timezone.now(),
            set_depth=60,
            set_spring=1,
            set_cone=1,
            depth=10,
            pressure=100,
            folder="FIELD001",
            set_device=device,
            land_block=block,
            land_ledger=ledger,
        )

        response = self.client.get(self.detail_url())

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'href="{self.report_url(ledger)}"')
