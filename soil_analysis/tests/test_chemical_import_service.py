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
    SoilChemicalMeasurement,
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

        # ブロックの作成
        for name in ChemicalImportService.BLOCK_NAMES:
            LandBlock.objects.get_or_create(name=name)

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

    def test_get_suggested_ledgers_excludes_used_ledger(self):
        """
        シナリオ:
        - 入力: 同一圃場に使用済み帳簿と未使用帳簿を用意する。
        - 処理: 圃場名から化学分析用の候補帳簿を取得する。
        - 期待値: 化学分析データに紐付け済みの帳簿は候補から除外されること。
        """
        unused_period = LandPeriod.objects.create(name="2024年春", year=2025)
        unused_ledger = LandLedger.objects.create(
            land=self.land,
            land_period=unused_period,
            sampling_date=date(2025, 4, 1),
            analytical_agency=self.company,
            crop=self.crop,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )
        SoilChemicalMeasurement.objects.create(
            land_ledger=self.ledger,
            ph=6.5,
            ec=0.1,
            source_file="used.xlsx",
        )

        ledgers = ChemicalImportService.get_suggested_ledgers("圃場A")

        self.assertNotIn(self.ledger, ledgers)
        self.assertIn(unused_ledger, ledgers)

    def test_get_suggested_ledgers_keeps_used_period_name_for_next_round(self):
        """
        シナリオ:
        - 入力: 2026年播種時を使用済みにし、同一圃場に2026年収穫時・2027年播種時・2027年収穫時を用意する。
        - 処理: 2ラウンド目の候補帳簿を圃場名から取得する。
        - 期待値: 使用済み帳簿と異なる時期名の帳簿は候補にならず、未使用の2027年播種時だけが返ること。
        """
        land = Land.objects.create(
            name="FIELD001（点検用圃場）",
            company=self.company,
            jma_city=self.city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="36.0,140.0",
        )
        used_period = LandPeriod.objects.create(name="播種時", year=2026)
        harvest_period = LandPeriod.objects.create(name="収穫時", year=2026)
        next_sowing_period = LandPeriod.objects.create(name="播種時", year=2027)
        next_harvest_period = LandPeriod.objects.create(name="収穫時", year=2027)
        used_ledger = LandLedger.objects.create(
            land=land,
            land_period=used_period,
            sampling_date=date(2026, 3, 3),
            analytical_agency=self.company,
            crop=self.crop,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )
        LandLedger.objects.create(
            land=land,
            land_period=harvest_period,
            sampling_date=date(2026, 9, 3),
            analytical_agency=self.company,
            crop=self.crop,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )
        expected_ledger = LandLedger.objects.create(
            land=land,
            land_period=next_sowing_period,
            sampling_date=date(2027, 3, 3),
            analytical_agency=self.company,
            crop=self.crop,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )
        LandLedger.objects.create(
            land=land,
            land_period=next_harvest_period,
            sampling_date=date(2027, 9, 3),
            analytical_agency=self.company,
            crop=self.crop,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )
        SoilChemicalMeasurement.objects.create(
            land_ledger=used_ledger,
            ph=6.5,
            ec=0.1,
            source_file="stage01.xlsx",
        )

        ledgers = ChemicalImportService.get_suggested_ledgers("FIELD001（点検用圃場）")

        self.assertEqual(ledgers, [expected_ledger])

    def test_get_suggested_ledgers_uses_first_unused_period_for_first_round(self):
        """
        シナリオ:
        - 入力: 3圃場に2026年播種時と2027年播種時の未使用帳簿を用意する。
        - 処理: 1ラウンド目の候補帳簿を圃場名から取得する。
        - 期待値: 最初の未使用LandPeriodである2026年播種時の3帳簿だけが返ること。
        """
        company = Company.objects.create(
            name="Round Test Company", category=self.company.category
        )
        first_period = LandPeriod.objects.create(name="播種時", year=2026)
        next_period = LandPeriod.objects.create(name="播種時", year=2027)
        expected_ledgers = []
        for number in range(1, 4):
            land = Land.objects.create(
                name=f"FIELD00{number}（点検用圃場）",
                company=company,
                jma_city=self.city,
                cultivation_type=self.cultivation_type,
                owner=self.user,
                center="36.0,140.0",
            )
            expected_ledgers.append(
                LandLedger.objects.create(
                    land=land,
                    land_period=first_period,
                    sampling_date=date(2026, 3, 3),
                    analytical_agency=company,
                    crop=self.crop,
                    sampling_method=self.sampling_method,
                    sampling_staff=self.user,
                )
            )
            LandLedger.objects.create(
                land=land,
                land_period=next_period,
                sampling_date=date(2027, 3, 3),
                analytical_agency=company,
                crop=self.crop,
                sampling_method=self.sampling_method,
                sampling_staff=self.user,
            )

        ledgers = ChemicalImportService.get_suggested_ledgers("FIELD001（点検用圃場）")

        self.assertEqual(ledgers, expected_ledgers)

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

        result = ChemicalImportService.save_import_data(
            rows_data, source_file="test_file.xlsx"
        )
        self.assertEqual(result["created"], 1)  # 圃場単位で1つ作成されるはず

        from soil_analysis.models import SoilChemicalMeasurement

        analysis = SoilChemicalMeasurement.objects.filter(
            land_ledger=self.ledger
        ).first()
        self.assertIsNotNone(analysis)
        self.assertEqual(analysis.ph, 6.5)
        self.assertEqual(analysis.source_file, "test_file.xlsx")

    def test_to_float_error_message_japanese(self):
        """数値変換失敗時のエラーメッセージに日本語カラム名が含まれること"""
        with self.assertRaises(ValueError) as cm:
            KawadaRow.parse_numeric_value("invalid", 10, "交換性石灰")

        self.assertIn("交換性石灰", str(cm.exception))
        self.assertIn("数値変換失敗", str(cm.exception))

    def test_from_excel_row_error_propagation(self):
        """Excelからのパース時に日本語カラム名が伝播すること"""
        # row index 7 is cao (交換性石灰)
        bad_row = [None] * 20
        bad_row[7] = "不適切な値"

        with self.assertRaises(ValueError) as cm:
            KawadaRow.from_excel_row(tuple(bad_row), 10)

    def test_save_import_data_with_duplicate_ledger(self):
        """同一取り込み内で同じ帳簿が指定された場合、後のデータで更新されること"""
        import dataclasses

        row1 = KawadaRow(
            row_number=4,
            analysis_number="A001",
            person_name="テスト太郎",
            land_name="圃場A",
            crop="キャベツ",
            ph=6.0,
            ec=0.1,
        )
        row2 = KawadaRow(
            row_number=5,
            analysis_number="A002",
            person_name="テスト太郎",
            land_name="圃場A (修正)",
            crop="キャベツ",
            ph=7.0,
            ec=0.2,
        )

        rows_data = [
            {"row_data": dataclasses.asdict(row1), "land_ledger_id": self.ledger.id},
            {"row_data": dataclasses.asdict(row2), "land_ledger_id": self.ledger.id},
        ]

        result = ChemicalImportService.save_import_data(
            rows_data, source_file="updated_file.xlsx"
        )

        # 重複チェックが削除されたため、エラーは出ず、1件として処理される
        # (すでに1件目の時点で ledger_to_latest_entry により上書きされている)
        self.assertEqual(result["created"], 1)
        self.assertEqual(result["error_count"], 0)

        from soil_analysis.models import SoilChemicalMeasurement

        analysis = SoilChemicalMeasurement.objects.filter(
            land_ledger=self.ledger
        ).first()
        self.assertIsNotNone(analysis)
        # 後の方のデータ(row2)のph=7.0が反映されているはず
        self.assertEqual(analysis.ph, 7.0)
        self.assertEqual(analysis.source_file, "updated_file.xlsx")

    def test_save_import_data_updates_only_selected_ledgers(self):
        """
        シナリオ:
        - 入力: 既存の化学分析がある台帳と、今回の取り込み対象台帳を用意する。
        - 処理: 今回対象の台帳だけを rows_data に渡して保存する。
        - 期待値: rows_data に含めていない既存台帳の化学分析値は変更されないこと。
        """
        import dataclasses

        from soil_analysis.models import SoilChemicalMeasurement

        other_period = LandPeriod.objects.create(name="2024年秋", year=2024)
        other_ledger = LandLedger.objects.create(
            land=self.land,
            land_period=other_period,
            sampling_date=date(2024, 10, 1),
            analytical_agency=self.company,
            crop=self.crop,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )
        SoilChemicalMeasurement.objects.create(
            land_ledger=other_ledger,
            ph=5.5,
            ec=0.1,
            source_file="existing.xlsx",
        )

        row = KawadaRow(
            row_number=4,
            analysis_number="A003",
            person_name="テスト太郎",
            land_name="圃場A",
            crop="キャベツ",
            ph=7.2,
            ec=0.3,
        )
        rows_data = [
            {"row_data": dataclasses.asdict(row), "land_ledger_id": self.ledger.id}
        ]

        result = ChemicalImportService.save_import_data(
            rows_data, source_file="selected_only.xlsx"
        )

        self.assertEqual(result["created"], 1)
        other_measurement = SoilChemicalMeasurement.objects.get(
            land_ledger=other_ledger
        )
        self.assertEqual(other_measurement.ph, 5.5)
        self.assertEqual(other_measurement.source_file, "existing.xlsx")
