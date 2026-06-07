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
        """
        シナリオ:
        - 入力: 正常な化学分析データを持つ帳簿。
        - 処理: 標準レポート画面(standard_report)を表示。
        - 期待値: ステータス200、正しいテンプレートの使用、正常判定、およびレビュー未登録時の「評価する」導線が表示されていること。
        """
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
        self.assertContains(response, "化学分析と物理性（9ブロック）の診断結果")
        self.assertContains(response, "pH・ECともに適正範囲内です")
        self.assertContains(response, "物理性")
        self.assertContains(response, "良好")
        self.assertContains(response, "注意")
        self.assertContains(response, "不良")
        self.assertContains(response, "※数値は5点平均硬度(kPa)")
        self.assertContains(response, "圃場単位の分析値に基づく判定です")
        self.assertContains(response, "テスト株式会社")
        self.assertContains(response, "専門家評価")
        self.assertContains(
            response, "この台帳にはまだ評価コメントが登録されていません。"
        )
        self.assertContains(response, "評価する")

    def test_view_displays_warning(self):
        """
        シナリオ:
        - 入力: 異常な化学分析データ（高pH低EC等）を持つ帳簿。
        - 処理: 標準レポート画面を表示。
        - 期待値: 「石灰成分の過剰」「肥料成分の不足」等の警告メッセージが表示されていること。
        """
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
        self.assertContains(response, "警告：Base Saturation(塩基飽和度)が過剰です。")
        self.assertContains(
            response, "警告：Humus(腐植)が不足しています。堆肥の投入を推奨します。"
        )

    def test_view_displays_insufficient_data(self):
        """
        シナリオ:
        - 入力: 化学分析データが紐付いていない帳簿。
        - 処理: 標準レポート画面を表示。
        - 期待値: 「判定に必要なデータが不足しています」というメッセージが表示されていること。
        """
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

    def test_view_displays_hardness_data(self):
        """
        シナリオ:
        - 入力: 土壌硬度データが紐付いている帳簿。
        - 処理: 標準レポート画面を表示。
        - 期待値: 測定値（kPa）が正しく画面に表示されていること。
        """
        # A1ブロックに硬度データを追加
        from soil_analysis.models import SoilHardnessMeasurement, Device
        from django.utils import timezone

        device = Device.objects.create(name="Test Device")
        SoilHardnessMeasurement.objects.create(
            land_ledger=self.ledger,
            land_block=self.block_a1,
            set_device=device,
            set_memory=1,
            set_datetime=timezone.now(),
            set_depth=60,
            set_spring=1,
            set_cone=1,
            depth=10,
            pressure=1200,
            folder="test",
        )

        url = reverse(
            "soil:standard_report",
            kwargs={"company_id": self.company.id, "land_ledger_id": self.ledger.id},
        )
        response = self.client.get(url)

        self.assertContains(response, "1,200")
        self.assertContains(response, "kPa")

    def test_view_displays_dynamic_sampling_method(self):
        """
        シナリオ:
        - 入力: 9点法でサンプリングされた帳簿。
        - 処理: 標準レポート画面を表示。
        - 期待値: 注釈や説明文が「9点法」に合わせた内容に動的に変化していること。
        """
        # 9点法の帳簿を作成
        sampling_method_9 = SamplingMethod.objects.create(name="9点法", times=9)
        ledger_9 = LandLedger.objects.create(
            land=self.land,
            land_period=LandPeriod.objects.create(name="2025 春", year=2025),
            sampling_date=date(2025, 4, 1),
            analytical_agency=self.company,
            crop=self.crop,
            sampling_method=sampling_method_9,
            sampling_staff=self.user,
        )

        url = reverse(
            "soil:standard_report",
            kwargs={"company_id": self.company.id, "land_ledger_id": ledger_9.id},
        )
        response = self.client.get(url)

        self.assertContains(response, "※数値は9点平均硬度(kPa)")
        self.assertContains(response, "9箇所</strong>で貫入計測を行う「9点法」")
        self.assertContains(response, "ブロック内の9箇所の測定値を深度ごとに平均化")
