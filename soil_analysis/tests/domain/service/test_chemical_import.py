from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from openpyxl import Workbook

from soil_analysis.management.commands.chemical_load_data import (
    BLOCK_IDS,
    Command,
    ParsedRow,
    parse_kawada_worksheet,
)
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
    LandBlock,
    LandLedger,
    LandPeriod,
    LandScoreChemical,
    SamplingMethod,
)


class ChemicalImportServiceTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.user = user_model.objects.create_user(username="staff", password="x")
        category = CompanyCategory.objects.create(name="農業法人")
        company = Company.objects.create(name="テスト法人", category=category)
        crop = Crop.objects.create(name="キャベツ")
        cultivation = CultivationType.objects.create(name="露地")
        jma_area = JmaArea.objects.create(code="123456", name="test")
        jma_pref = JmaPrefecture.objects.create(code="654321", jma_area=jma_area, name="静岡")
        jma_region = JmaRegion.objects.create(code="111111", jma_prefecture=jma_pref, name="西部")
        jma_city = JmaCity.objects.create(code="2222222", jma_region=jma_region, name="浜松")
        land = Land.objects.create(
            name="圃場A",
            jma_city=jma_city,
            center="35.1,139.1",
            area=100,
            company=company,
            cultivation_type=cultivation,
            owner=self.user,
        )
        period = LandPeriod.objects.create(year=2026, name="定植時")
        sampling_method = SamplingMethod.objects.create(name="5点法", times=5)
        self.ledger = LandLedger.objects.create(
            sampling_date=date(2026, 5, 1),
            analytical_agency=company,
            crop=crop,
            land=land,
            land_period=period,
            sampling_method=sampling_method,
            sampling_staff=self.user,
        )
        land_b = Land.objects.create(
            name="圃場B",
            jma_city=jma_city,
            center="35.2,139.2",
            area=120,
            company=company,
            cultivation_type=cultivation,
            owner=self.user,
        )
        self.ledger_b = LandLedger.objects.create(
            sampling_date=date(2026, 5, 2),
            analytical_agency=company,
            crop=crop,
            land=land_b,
            land_period=period,
            sampling_method=sampling_method,
            sampling_staff=self.user,
        )
        for block_id in BLOCK_IDS:
            LandBlock.objects.create(id=block_id, name=f"Block{block_id}")

    def test_parse_kawada_worksheet_success_and_conversion(self):
        wb = Workbook()
        ws = wb.active
        # 川田フォーマットは3行目がヘッダー、4行目からデータ
        # A=分析番号, B=氏名, C=圃場名, D=作物, E〜T=化学データ
        ws.append([])  # 1行目: 空
        ws.append([])  # 2行目: 空
        ws.append(["分析番号", "氏名", "圃場名", "作物", "EC", "pH", "CEC", "CaO", "MgO", "K2O", "石灰飽和度", "苦土飽和度", "加里飽和度", "塩基飽和度", "P2O5", "リン酸吸収係数", "NH4-N", "NO3-N", "腐植", "仮比重"])  # 3行目: ヘッダー
        ws.append(["001", "田中", "圃場A", "キャベツ", "1.2", "6.5", "15", "100", "20", "30", "60", "20", "10", "50%", "60", "800", "3", "4", "2.5%", "0.8"])  # 4行目: データ
        result = parse_kawada_worksheet(ws)
        self.assertEqual(len(result.errors), 0)
        self.assertEqual(len(result.rows), 1)
        self.assertEqual(result.rows[0].land_name, "圃場A")
        self.assertEqual(result.rows[0].values["humus"], 2.5)
        self.assertEqual(result.rows[0].values["base_saturation"], 50.0)

    def test_parse_kawada_worksheet_missing_required_columns(self):
        wb = Workbook()
        ws = wb.active
        ws.append([])  # 1行目: 空
        ws.append([])  # 2行目: 空
        # 3行目: ヘッダー（列が少なすぎる）
        result = parse_kawada_worksheet(ws)
        self.assertEqual(result.rows, [])
        self.assertTrue(len(result.errors) > 0)

    def test_resolve_target_ledger_by_land_name_and_period(self):
        row_a = ParsedRow(row_number=4, land_name="圃場A", values={})
        row_b = ParsedRow(row_number=5, land_name="圃場B", values={})

        ledger_a, warning_a = Command._resolve_target_ledger(row_a, self.ledger)
        ledger_b, warning_b = Command._resolve_target_ledger(row_b, self.ledger)

        self.assertEqual(warning_a, None)
        self.assertEqual(warning_b, None)
        self.assertEqual(ledger_a.id, self.ledger.id)
        self.assertEqual(ledger_b.id, self.ledger_b.id)
