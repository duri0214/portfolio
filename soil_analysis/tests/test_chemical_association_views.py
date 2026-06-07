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
