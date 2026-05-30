from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from soil_analysis.models import (
    Company,
    CompanyCategory,
    Land,
    LandPeriod,
    LandLedger,
    LandBlock,
    SoilChemicalMeasurement,
    JmaArea,
    JmaPrefecture,
    JmaRegion,
    JmaCity,
    CultivationType,
    Crop,
    SamplingMethod,
)


class StandardReportViewTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="testuser")

        # マスタ類の作成
        category = CompanyCategory.objects.create(name="テストカテゴリ")
        self.company = Company.objects.create(name="テスト株式会社", category=category)

        area = JmaArea.objects.create(code="01", name="テストエリア")
        pref = JmaPrefecture.objects.create(code="0101", name="テスト県", jma_area=area)
        region = JmaRegion.objects.create(
            code="010101", name="テスト地域", jma_prefecture=pref
        )
        self.city = JmaCity.objects.create(
            code="0101011", name="テスト市", jma_region=region
        )

        self.cultivation_type = CultivationType.objects.create(name="露地")
        self.crop = Crop.objects.create(name="キャベツ")
        self.sampling_method = SamplingMethod.objects.create(name="5点法", times=5)

        self.land = Land.objects.create(
            name="テスト圃場",
            company=self.company,
            jma_city=self.city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="36.0,140.0",
        )

        self.period = LandPeriod.objects.create(name="2024 春", year=2024)
        self.ledger = LandLedger.objects.create(
            land=self.land,
            land_period=self.period,
            sampling_date=date(2024, 4, 1),
            analytical_agency=self.company,
            crop=self.crop,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )
        self.block_a1 = LandBlock.objects.get_or_create(name="A1")[0]

        # 正常範囲内のデータを投入
        SoilChemicalMeasurement.objects.create(
            land_ledger=self.ledger,
            ph=6.5,
            ec=0.3,
            nh4n=2.0,
            no3n=10.0,
            cao=100.0,
            mgo=30.0,
            k2o=20.0,
            cec=15.0,
            base_saturation=75.0,
            phosphorus_absorption=1000.0,
            p2o5=20.0,
            humus=4.0,
            bulk_density=1.0,
        )

    def test_view_displays_assessment(self):
        url = reverse(
            "soil:standard_report",
            kwargs={"company_id": self.company.id, "land_ledger_id": self.ledger.id},
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(
            response, "soil_analysis/land_report/standard_report.html"
        )

        # 判定結果が表示されていること
        self.assertContains(response, "圃場属性")
        self.assertContains(response, "化学分析の診断結果")
        self.assertContains(response, "pH・ECともに適正範囲内です")
        self.assertContains(response, "圃場単位の分析値に基づく判定です")
        self.assertContains(response, "テスト株式会社")

    def test_view_displays_warning(self):
        # 異常値を投入した別の帳簿を作成
        ledger_bad = LandLedger.objects.create(
            land=self.land,
            land_period=LandPeriod.objects.create(name="2024 秋", year=2024),
            sampling_date=date(2024, 10, 1),
            analytical_agency=self.company,
            crop=self.crop,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )
        SoilChemicalMeasurement.objects.create(
            land_ledger=ledger_bad,
            ph=7.5,
            ec=0.05,  # 高pH低EC
            cao=0.0,
            mgo=0.0,
            k2o=0.0,
            cec=0.0,
            base_saturation=120.0,  # 過剰警告
            phosphorus_absorption=0.0,
            p2o5=0.0,
            humus=2.0,  # 腐植不足警告
            bulk_density=0.0,
        )

        url = reverse(
            "soil:standard_report",
            kwargs={"company_id": self.company.id, "land_ledger_id": ledger_bad.id},
        )
        response = self.client.get(url)

        self.assertContains(response, "石灰成分の過剰")
        self.assertContains(response, "肥料成分の不足")
        self.assertContains(
            response, "警告：Base Saturation(塩基飽和度)が過剰です（120.0）"
        )
        self.assertContains(response, "警告：Humus(腐植)が2.0%と不足しています")

    def test_view_displays_insufficient_data(self):
        # データがない帳簿
        ledger_empty = LandLedger.objects.create(
            land=self.land,
            land_period=LandPeriod.objects.create(name="2024 冬", year=2024),
            sampling_date=date(2024, 12, 1),
            analytical_agency=self.company,
            crop=self.crop,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )

        url = reverse(
            "soil:standard_report",
            kwargs={"company_id": self.company.id, "land_ledger_id": ledger_empty.id},
        )
        response = self.client.get(url)

        self.assertContains(response, "判定に必要なデータが不足しています")
