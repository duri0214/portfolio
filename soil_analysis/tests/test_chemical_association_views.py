from datetime import date
import io
import zipfile

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from openpyxl import load_workbook

from soil_analysis.domain.service.chemical_import_service import ChemicalImportService

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
    LandBlock,
    SoilChemicalMeasurement,
)


class ChemicalAssociationViewsTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="testuser")

        category = CompanyCategory.objects.create(name="テストカテゴリ")
        self.company = Company.objects.create(name="Test Company", category=category)
        area = JmaArea.objects.create(code="01", name="テストエリア")
        pref = JmaPrefecture.objects.create(code="0101", name="テスト県", jma_area=area)
        region = JmaRegion.objects.create(
            code="010101", name="テスト地域", jma_prefecture=pref
        )
        city = JmaCity.objects.create(
            code="0101011", name="テスト市", jma_region=region
        )

        cultivation_type = CultivationType.objects.create(name="露地")
        crop = Crop.objects.create(name="キャベツ")
        sampling_method = SamplingMethod.objects.create(name="5点法", times=5)
        period = LandPeriod.objects.create(name="2024年春", year=2024)

        # LandBlockを作成 (ChemicalImportService.BLOCK_NAMESに対応)
        for name in ["A1", "A3", "B2", "C1", "C3"]:
            LandBlock.objects.create(name=name)

        land = Land.objects.create(
            name="圃場A",
            company=self.company,
            jma_city=city,
            cultivation_type=cultivation_type,
            owner=self.user,
            center="36.0,140.0",
        )
        self.ledger = LandLedger.objects.create(
            land=land,
            land_period=period,
            sampling_date=date(2024, 4, 1),
            analytical_agency=self.company,
            crop=crop,
            sampling_method=sampling_method,
            sampling_staff=self.user,
        )

    def test_upload_form_does_not_show_target_ledger_field(self):
        response = self.client.get(reverse("soil:chemical_upload"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "川田研究所 XLSX")
        self.assertNotContains(response, 'id="id_land_ledger_id"')

    def test_row_confirmation_flow_works_without_base_ledger(self):
        session = self.client.session
        session["chemical_import_session"] = {
            "rows": [
                {
                    "row_data": {
                        "row_number": 4,
                        "analysis_number": "A001",
                        "person_name": "テスト太郎",
                        "land_name": "圃場A",
                        "crop": "キャベツ",
                        "ec": 0.1,
                        "ph": 6.5,
                        "cec": None,
                        "cao": None,
                        "mgo": None,
                        "k2o": None,
                        "lime_saturation": None,
                        "magnesia_saturation": None,
                        "potash_saturation": None,
                        "base_saturation": None,
                        "p2o5": None,
                        "phosphorus_absorption": None,
                        "nh4n": None,
                        "no3n": None,
                        "humus": None,
                        "bulk_density": None,
                    },
                    "selected_ledger_id": None,
                    "status": "pending",
                }
            ],
            "total_rows": 1,
        }
        session.save()

        row_url = reverse(
            "soil:chemical_association_field_row", kwargs={"row_index": 0}
        )
        response = self.client.get(row_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "圃場A")

        response = self.client.post(row_url, {"land_ledger": self.ledger.id})
        self.assertRedirects(response, reverse("soil:chemical_association"))

        updated_session = self.client.session["chemical_import_session"]["rows"][0]
        self.assertEqual(updated_session["status"], "confirmed")
        self.assertEqual(updated_session["selected_ledger_id"], self.ledger.id)

    def test_row_confirmation_shows_year_and_sampling_date_in_ledger_options(self):
        """
        シナリオ:
        - 入力: 同一圃場に、同じ時期名で年度が異なる帳簿を用意する。
        - 処理: 化学分析の行別帳簿関連付け画面を表示する。
        - 期待値: 候補帳簿の選択肢に年度と採土日が表示され、帳簿を区別できること。
        """
        period = LandPeriod.objects.create(name="播種時", year=2025)
        other_ledger = LandLedger.objects.create(
            land=self.ledger.land,
            land_period=period,
            sampling_date=date(2025, 4, 1),
            analytical_agency=self.company,
            crop=self.ledger.crop,
            sampling_method=self.ledger.sampling_method,
            sampling_staff=self.user,
        )
        session = self.client.session
        session["chemical_import_session"] = {
            "rows": [
                {
                    "row_data": {
                        "row_number": 4,
                        "analysis_number": "A001",
                        "person_name": "テスト太郎",
                        "land_name": "圃場A",
                        "crop": "キャベツ",
                        "ec": 0.1,
                        "ph": 6.5,
                        "cec": None,
                        "cao": None,
                        "mgo": None,
                        "k2o": None,
                        "lime_saturation": None,
                        "magnesia_saturation": None,
                        "potash_saturation": None,
                        "base_saturation": None,
                        "p2o5": None,
                        "phosphorus_absorption": None,
                        "nh4n": None,
                        "no3n": None,
                        "humus": None,
                        "bulk_density": None,
                    },
                    "selected_ledger_id": None,
                    "status": "pending",
                }
            ],
            "total_rows": 1,
        }
        session.save()

        response = self.client.get(
            reverse("soil:chemical_association_field_row", kwargs={"row_index": 0})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "2024 2024年春 / 採土日: 2024-04-01")
        self.assertContains(response, "2025 播種時 / 採土日: 2025-04-01")
        self.assertContains(response, f'value="{other_ledger.id}"')

    def test_row_confirmation_excludes_used_chemical_ledger_options(self):
        """
        シナリオ:
        - 入力: 化学分析データに紐付け済みの帳簿と未使用帳簿を用意する。
        - 処理: 化学分析の行別帳簿関連付け画面を表示する。
        - 期待値: 使用済み帳簿は候補帳簿にも全帳簿にも表示されず、未使用帳簿だけ選べること。
        """
        unused_period = LandPeriod.objects.create(name="2024年秋", year=2024)
        unused_ledger = LandLedger.objects.create(
            land=self.ledger.land,
            land_period=unused_period,
            sampling_date=date(2024, 10, 1),
            analytical_agency=self.company,
            crop=self.ledger.crop,
            sampling_method=self.ledger.sampling_method,
            sampling_staff=self.user,
        )
        SoilChemicalMeasurement.objects.create(
            land_ledger=self.ledger,
            ph=6.5,
            ec=0.1,
            source_file="used.xlsx",
        )
        session = self.client.session
        session["chemical_import_session"] = {
            "rows": [
                {
                    "row_data": {
                        "row_number": 4,
                        "analysis_number": "A001",
                        "person_name": "テスト太郎",
                        "land_name": "圃場A",
                        "crop": "キャベツ",
                        "ec": 0.1,
                        "ph": 6.5,
                        "cec": None,
                        "cao": None,
                        "mgo": None,
                        "k2o": None,
                        "lime_saturation": None,
                        "magnesia_saturation": None,
                        "potash_saturation": None,
                        "base_saturation": None,
                        "p2o5": None,
                        "phosphorus_absorption": None,
                        "nh4n": None,
                        "no3n": None,
                        "humus": None,
                        "bulk_density": None,
                    },
                    "selected_ledger_id": None,
                    "status": "pending",
                }
            ],
            "total_rows": 1,
        }
        session.save()

        response = self.client.get(
            reverse("soil:chemical_association_field_row", kwargs={"row_index": 0})
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, f'value="{self.ledger.id}"')
        self.assertContains(response, f'value="{unused_ledger.id}"')

    def test_association_list_candidate_count_uses_oldest_unused_year_for_land(self):
        """
        シナリオ:
        - 入力: 3圃場の2026年播種時を使用済みにし、2026年収穫時と2027年播種時の未使用帳簿を用意する。
        - 処理: 化学分析の関連付け一覧画面を表示する。
        - 期待値: FIELD001に一致する最古未使用年度の帳簿だけを数え、2026年収穫時の1件になること。
        """
        used_period = LandPeriod.objects.create(name="播種時", year=2026)
        harvest_period = LandPeriod.objects.create(name="収穫時", year=2026)
        next_sowing_period = LandPeriod.objects.create(name="播種時", year=2027)
        next_harvest_period = LandPeriod.objects.create(name="収穫時", year=2027)
        expected_ledger = None
        for number in range(1, 4):
            land = Land.objects.create(
                name=f"FIELD00{number}（点検用圃場）",
                company=self.company,
                jma_city=self.ledger.land.jma_city,
                cultivation_type=self.ledger.land.cultivation_type,
                owner=self.user,
                center="36.0,140.0",
            )
            used_ledger = LandLedger.objects.create(
                land=land,
                land_period=used_period,
                sampling_date=date(2026, 3, 3),
                analytical_agency=self.company,
                crop=self.ledger.crop,
                sampling_method=self.ledger.sampling_method,
                sampling_staff=self.user,
            )
            harvest_ledger = LandLedger.objects.create(
                land=land,
                land_period=harvest_period,
                sampling_date=date(2026, 9, 3),
                analytical_agency=self.company,
                crop=self.ledger.crop,
                sampling_method=self.ledger.sampling_method,
                sampling_staff=self.user,
            )
            if number == 1:
                expected_ledger = harvest_ledger
            LandLedger.objects.create(
                land=land,
                land_period=next_sowing_period,
                sampling_date=date(2027, 3, 3),
                analytical_agency=self.company,
                crop=self.ledger.crop,
                sampling_method=self.ledger.sampling_method,
                sampling_staff=self.user,
            )
            LandLedger.objects.create(
                land=land,
                land_period=next_harvest_period,
                sampling_date=date(2027, 9, 3),
                analytical_agency=self.company,
                crop=self.ledger.crop,
                sampling_method=self.ledger.sampling_method,
                sampling_staff=self.user,
            )
            SoilChemicalMeasurement.objects.create(
                land_ledger=used_ledger,
                ph=6.5,
                ec=0.1,
                source_file="stage01.xlsx",
            )
        session = self.client.session
        session["chemical_import_session"] = {
            "rows": [
                {
                    "row_data": {
                        "row_number": 4,
                        "analysis_number": "A101",
                        "person_name": "テスト太郎",
                        "land_name": "FIELD001（点検用圃場）",
                        "crop": "キャベツ",
                    },
                    "selected_ledger_id": None,
                    "status": "pending",
                }
            ],
            "total_rows": 1,
        }
        session.save()

        response = self.client.get(reverse("soil:chemical_association"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["rows"][0]["suggested_count"], 1)
        self.assertEqual(
            response.context["rows"][0]["selected_ledger"],
            None,
        )
        suggested_ledgers = ChemicalImportService.get_suggested_ledgers(
            "FIELD001（点検用圃場）"
        )
        self.assertEqual(suggested_ledgers, [expected_ledger])

    def test_association_list_shows_selected_ledger_year_and_sampling_date(self):
        """
        シナリオ:
        - 入力: 関連付け済み行を含む化学分析取り込みセッションを用意する。
        - 処理: 化学分析の関連付け一覧画面を表示する。
        - 期待値: Excel行番号として表示され、関連付け済み帳簿に年度と採土日が表示されること。
        """
        session = self.client.session
        session["chemical_import_session"] = {
            "rows": [
                {
                    "row_data": {
                        "row_number": 4,
                        "analysis_number": "A001",
                        "person_name": "テスト太郎",
                        "land_name": "圃場A",
                        "crop": "キャベツ",
                    },
                    "selected_ledger_id": self.ledger.id,
                    "status": "confirmed",
                }
            ],
            "total_rows": 1,
        }
        session.save()

        response = self.client.get(reverse("soil:chemical_association"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "処理済み - Excel行: 4")
        self.assertContains(response, "2024 2024年春")
        self.assertContains(response, "採土日: 2024-04-01")

    def test_row_confirmation_rejects_used_chemical_ledger_post(self):
        """
        シナリオ:
        - 入力: 化学分析データに紐付け済みの帳簿IDをPOSTする。
        - 処理: 行別帳簿関連付け画面で帳簿を確定しようとする。
        - 期待値: 使用済み帳簿は確定されず、同じ行の関連付け画面に戻ること。
        """
        SoilChemicalMeasurement.objects.create(
            land_ledger=self.ledger,
            ph=6.5,
            ec=0.1,
            source_file="used.xlsx",
        )
        session = self.client.session
        session["chemical_import_session"] = {
            "rows": [
                {
                    "row_data": {
                        "row_number": 4,
                        "analysis_number": "A001",
                        "person_name": "テスト太郎",
                        "land_name": "圃場A",
                        "crop": "キャベツ",
                        "ec": 0.1,
                        "ph": 6.5,
                        "cec": None,
                        "cao": None,
                        "mgo": None,
                        "k2o": None,
                        "lime_saturation": None,
                        "magnesia_saturation": None,
                        "potash_saturation": None,
                        "base_saturation": None,
                        "p2o5": None,
                        "phosphorus_absorption": None,
                        "nh4n": None,
                        "no3n": None,
                        "humus": None,
                        "bulk_density": None,
                    },
                    "selected_ledger_id": None,
                    "status": "pending",
                }
            ],
            "total_rows": 1,
        }
        session.save()

        row_url = reverse(
            "soil:chemical_association_field_row", kwargs={"row_index": 0}
        )
        response = self.client.post(row_url, {"land_ledger": self.ledger.id})

        self.assertRedirects(response, row_url)
        updated_session = self.client.session["chemical_import_session"]["rows"][0]
        self.assertEqual(updated_session["status"], "pending")
        self.assertIsNone(updated_session["selected_ledger_id"])

    def test_success_summary_orders_by_land_name_ascending(self):
        """
        シナリオ:
        - 入力: FIELD003, FIELD002, FIELD001 の順に保存結果の帳簿IDをセッションへ入れる。
        - 処理: 化学分析の関連付け完了画面を表示する。
        - 期待値: 集計表示はセッション順ではなく圃場名昇順で FIELD001, FIELD002, FIELD003 になること。
        """
        period = LandPeriod.objects.create(name="播種時", year=2026)
        ledgers = []
        for land_name in (
            "FIELD003（点検用圃場）",
            "FIELD002（点検用圃場）",
            "FIELD001（点検用圃場）",
        ):
            land = Land.objects.create(
                name=land_name,
                company=self.company,
                jma_city=self.ledger.land.jma_city,
                cultivation_type=self.ledger.land.cultivation_type,
                owner=self.user,
                center="36.0,140.0",
            )
            ledger = LandLedger.objects.create(
                land=land,
                land_period=period,
                sampling_date=date(2026, 3, 3),
                analytical_agency=self.company,
                crop=self.ledger.crop,
                sampling_method=self.ledger.sampling_method,
                sampling_staff=self.user,
            )
            SoilChemicalMeasurement.objects.create(
                land_ledger=ledger,
                ph=6.5,
                ec=0.1,
                source_file="stage02.xlsx",
            )
            ledgers.append(ledger)
        session = self.client.session
        session["chemical_import_result"] = {
            "created": 3,
            "updated": 0,
            "ledger_ids": [ledger.id for ledger in ledgers],
            "error_count": 0,
        }
        session.save()

        response = self.client.get(reverse("soil:chemical_association_success"))

        self.assertEqual(response.status_code, 200)
        summary_names = [row["land_name"] for row in response.context["ledger_summary"]]
        self.assertEqual(
            summary_names,
            [
                "FIELD001（点検用圃場）",
                "FIELD002（点検用圃場）",
                "FIELD003（点検用圃場）",
            ],
        )

    def test_save_all_redirects_to_success(self):
        session = self.client.session
        session["chemical_import_session"] = {
            "rows": [
                {
                    "row_data": {
                        "row_number": 4,
                        "analysis_number": "A001",
                        "person_name": "テスト太郎",
                        "land_name": "圃場A",
                        "crop": "キャベツ",
                        "ec": 0.1,
                        "ph": 6.5,
                        "cec": 10.0,
                        "cao": 100.0,
                        "mgo": 50.0,
                        "k2o": 30.0,
                        "lime_saturation": 80.0,
                        "magnesia_saturation": 15.0,
                        "potash_saturation": 5.0,
                        "base_saturation": 100.0,
                        "p2o5": 20.0,
                        "phosphorus_absorption": 1000.0,
                        "nh4n": 1.0,
                        "no3n": 2.0,
                        "humus": 3.0,
                        "bulk_density": 1.0,
                    },
                    "selected_ledger_id": self.ledger.id,
                    "status": "confirmed",
                }
            ],
            "total_rows": 1,
            "source_file": "web_upload.xlsx",
        }
        session.save()

        url = reverse("soil:chemical_association")
        # btn_save_all を含めて POST
        response = self.client.post(url, {"btn_save_all": "1"})

        # 成功画面へのリダイレクトを期待
        self.assertRedirects(response, reverse("soil:chemical_association_success"))

        # セッションがクリアされていることを確認
        self.assertNotIn("chemical_import_session", self.client.session)
        self.assertIn("chemical_import_result", self.client.session)

        # 実際にデータが保存され、source_fileがセットされているか確認
        from soil_analysis.models import SoilChemicalMeasurement

        analysis = SoilChemicalMeasurement.objects.filter(
            land_ledger=self.ledger
        ).first()
        self.assertIsNotNone(analysis)
        self.assertEqual(analysis.source_file, "web_upload.xlsx")

    def test_chemical_sample_download_returns_stage_workbooks(self):
        """
        シナリオ:
        - 入力: サンプルExcelダウンロードURLへGETする。
        - 処理: 返却されたZIP内の stage01/stage02/duplicate Excel を読み込む。
        - 期待値: 各Excelが川田形式としてパースでき、連続登録検証用の行を含むこと。
        """
        response = self.client.get(reverse("soil:chemical_download_sample"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/zip")

        with zipfile.ZipFile(io.BytesIO(response.content)) as archive:
            names = set(archive.namelist())
            self.assertIn("chemical_stage01.xlsx", names)
            self.assertIn("chemical_stage02.xlsx", names)
            self.assertIn("chemical_duplicate.xlsx", names)
            for workbook_name in (
                "chemical_stage01.xlsx",
                "chemical_stage02.xlsx",
                "chemical_duplicate.xlsx",
            ):
                workbook = load_workbook(
                    io.BytesIO(archive.read(workbook_name)), data_only=True
                )
                parse_result = ChemicalImportService.parse_kawada_worksheet(
                    workbook.active
                )
                self.assertEqual(parse_result.errors, [])
                self.assertEqual(len(parse_result.rows), 3)
