from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from soil_analysis.domain.service.chemical_import_service import (
    ChemicalImportService,
    KawadaRow,
)
from soil_analysis.models import (
    Land,
    LandLedger,
    LandPeriod,
    Company,
    CompanyCategory,
    JmaArea,
    JmaPrefecture,
    JmaRegion,
    JmaCity,
    CultivationType,
    Crop,
    SamplingMethod,
    LandBlock,
)


class ChemicalImportServiceTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="testuser")

        # マスタ類の作成
        category = CompanyCategory.objects.create(name="テストカテゴリ")
        self.company = Company.objects.create(name="Test Company", category=category)

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

        # ブロックの作成 (ChemicalImportService.BLOCK_IDS = (1, 3, 5, 7, 9))
        for i in [1, 3, 5, 7, 9]:
            LandBlock.objects.get_or_create(id=i, defaults={"name": f"Block{i}"})

        self.period = LandPeriod.objects.create(name="2024年春", year=2024)
        self.land = Land.objects.create(
            name="圃場A",
            company=self.company,
            jma_city=self.city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="36.0,140.0",
        )
        self.ledger = LandLedger.objects.create(
            land=self.land,
            land_period=self.period,
            sampling_date=date(2024, 4, 1),
            analytical_agency=self.company,
            crop=self.crop,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )

    def test_get_suggested_ledgers_exact_match(self):
        """完全一致の圃場名で帳簿が検索できること"""
        ledgers = ChemicalImportService.get_suggested_ledgers("圃場A")
        self.assertEqual(len(ledgers), 1)
        self.assertEqual(ledgers[0].id, self.ledger.id)

    def test_get_suggested_ledgers_partial_match(self):
        """部分一致の圃場名で帳簿が検索できること"""
        ledgers = ChemicalImportService.get_suggested_ledgers("圃場")
        self.assertIn(self.ledger, ledgers)

    def test_get_suggested_ledgers_with_base_ledger_priority(self):
        """base_ledgerと同じ期間の帳簿が優先されること"""
        period2 = LandPeriod.objects.create(name="2024年秋", year=2024)
        ledger2 = LandLedger.objects.create(
            land=self.land,
            land_period=period2,
            sampling_date=date(2024, 10, 1),
            analytical_agency=self.company,
            crop=self.crop,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )

        # base_ledger_id を指定
        ledgers = ChemicalImportService.get_suggested_ledgers(
            "圃場A", base_ledger_id=self.ledger.id
        )
        self.assertEqual(ledgers[0].id, self.ledger.id)

        ledgers2 = ChemicalImportService.get_suggested_ledgers(
            "圃場A", base_ledger_id=ledger2.id
        )
        self.assertEqual(ledgers2[0].id, ledger2.id)

    def test_save_import_data(self):
        """データの保存ができること"""
        row = KawadaRow(
            row_number=4,
            analysis_number="A001",
            person_name="テスト太郎",
            land_name="圃場A",
            crop="キャベツ",
            ec=0.1,
            ph=6.5,
            cec=None,
            cao=None,
            mgo=None,
            k2o=None,
            lime_saturation=None,
            magnesia_saturation=None,
            potash_saturation=None,
            base_saturation=None,
            p2o5=None,
            phosphorus_absorption=None,
            nh4n=None,
            no3n=None,
            humus=None,
            bulk_density=None,
        )

        import dataclasses

        rows_data = [
            {"row_data": dataclasses.asdict(row), "land_ledger_id": self.ledger.id}
        ]

        result = ChemicalImportService.save_import_data(rows_data)
        self.assertEqual(result["created"], 5)  # 5ブロック分作成されるはず

        from soil_analysis.models import LandScoreChemical

        chemicals = LandScoreChemical.objects.filter(land_ledger=self.ledger)
        self.assertEqual(chemicals.count(), 5)
        self.assertEqual(chemicals.first().ph, 6.5)
        self.assertEqual(
            chemicals.first().remark, ChemicalImportService.REMARK_IMPORT_MODE
        )
