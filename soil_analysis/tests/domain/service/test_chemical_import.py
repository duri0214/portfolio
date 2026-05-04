from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from openpyxl import Workbook

from soil_analysis.domain.service.chemical_import import (
    BLOCK_NAMES,
    ParsedChemicalRow,
    import_chemical_rows,
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
        for block_name in BLOCK_NAMES:
            LandBlock.objects.create(name=block_name)

    def test_parse_kawada_worksheet_success_and_conversion(self):
        wb = Workbook()
        ws = wb.active
        ws.append(["圃場名", "EC", "NH4-N", "NO3-N", "pH", "CaO", "MgO", "K2O", "CEC", "腐植", "仮比重", "塩基飽和度", "CaO/MgO", "MgO/K2O", "リン酸吸収係数", "P2O5", "無機態N", "NH4/N比"])
        ws.append(["圃場A", "1.2", "3", "4", "6.5", "100", "20", "30", "15", "2.5%", "0.8", "50%", "5", "0.7", "800", "60", "7", "0.4"])
        rows, errors = parse_kawada_worksheet(ws)
        self.assertEqual(len(errors), 0)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].land_name, "圃場A")
        self.assertEqual(rows[0].values["humus"], 2.5)
        self.assertEqual(rows[0].values["base_saturation"], 50.0)

    def test_parse_kawada_worksheet_missing_required_columns(self):
        wb = Workbook()
        ws = wb.active
        ws.append(["圃場名", "EC"])
        ws.append(["圃場A", "1.2"])
        rows, errors = parse_kawada_worksheet(ws)
        self.assertEqual(rows, [])
        self.assertTrue(any("必須列不足" in error for error in errors))

    def test_import_chemical_rows_create_and_overwrite(self):
        values = {
            "ec": 1.0,
            "nh4n": 2.0,
            "no3n": 3.0,
            "total_nitrogen": 5.0,
            "nh4_per_nitrogen": 0.4,
            "ph": 6.5,
            "cao": 100.0,
            "mgo": 20.0,
            "k2o": 30.0,
            "base_saturation": 50.0,
            "cao_per_mgo": 5.0,
            "mgo_per_k2o": 0.7,
            "phosphorus_absorption": 800.0,
            "p2o5": 60.0,
            "cec": 15.0,
            "humus": 2.5,
            "bulk_density": 0.8,
        }
        row = ParsedChemicalRow(row_number=2, land_name="圃場A", values=values)

        created_count, updated_count, warnings = import_chemical_rows(
            parsed_rows=[row],
            row_ledger_map={2: self.ledger.id},
            overwrite=False,
        )
        self.assertEqual(created_count, 9)
        self.assertEqual(updated_count, 0)
        self.assertEqual(len(warnings), 0)
        self.assertEqual(LandScoreChemical.objects.filter(land_ledger=self.ledger).count(), 9)

        row2 = ParsedChemicalRow(row_number=2, land_name="圃場A", values={**values, "ec": 9.9})
        created_count2, updated_count2, warnings2 = import_chemical_rows(
            parsed_rows=[row2],
            row_ledger_map={2: self.ledger.id},
            overwrite=True,
        )
        self.assertEqual(created_count2, 0)
        self.assertEqual(updated_count2, 9)
        self.assertEqual(len(warnings2), 0)
        self.assertEqual(
            LandScoreChemical.objects.filter(land_ledger=self.ledger, ec=9.9).count(), 9
        )
