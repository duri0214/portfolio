from datetime import UTC, date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd
from django.core import management
from django.core.management.base import CommandError
from django.test import TestCase

from securities.models import Company, ReportDocument


class IndexViewTests(TestCase):
    def test_document_list_includes_incremental_search_data(self):
        """
        シナリオ:
        - Given: 提出者名とEDINETコードを持つ未予約の書類がある。
        - When: 書類一覧を表示する。
        - Then: 検索入力欄と、提出者名・EDINETコードを含む行データが表示される。
        """
        company = Company.objects.create(
            edinet_code="E00001",
            submitter_name="ＭＳ＆ＡＤテスト株式会社",
        )
        ReportDocument.objects.create(
            seq_number=1,
            doc_id="S1000001",
            ordinance_code="010",
            form_code="030000",
            period_start=date(2026, 1, 1),
            period_end=date(2026, 3, 31),
            submit_date_time=datetime(2026, 6, 30, 9, 0, tzinfo=UTC),
            doc_description="有価証券報告書",
            withdrawal_status="0",
            doc_info_edit_status="0",
            disclosure_status="0",
            xbrl_flag=True,
            pdf_flag=True,
            english_doc_flag=False,
            csv_flag=False,
            legal_status=False,
            company=company,
        )

        response = self.client.get("/securities/")

        self.assertContains(response, 'id="document-search"')
        self.assertContains(response, 'data-filer-name="ＭＳ＆ＡＤテスト株式会社"')
        self.assertContains(response, 'data-edinet-code="E00001"')
        self.assertContains(response, "一致する書類はありません。")

    def test_index_explains_submission_period_and_links_to_company_list(self):
        """
        Scenario:
        - Given: The securities report search screen is opened.
        - When: The index view is requested.
        - Then: The submission period explanation and fiscal year list link are shown.
        """
        response = self.client.get("/securities/")

        self.assertContains(response, "提出日時の期間")
        self.assertContains(response, 'href="/securities/companies/"')

    @patch("securities.views.XbrlService.fetch_report_doc_list")
    def test_post_without_company_guides_to_edinet_code_import(
        self, fetch_report_doc_list
    ):
        """
        シナリオ:
        - Given: 会社マスタが空である。
        - When: STEP 2で書類一覧の取得を実行する。
        - Then: STEP 1の取込案内を表示し、EDINET APIの取得処理を実行しない。
        """
        response = self.client.post("/securities/", follow=True)

        self.assertContains(response, "STEP 1の実施が必要です。")
        self.assertContains(response, "setup-required-alert")
        self.assertContains(response, "alert-danger")
        self.assertContains(response, "setup-required-shake")
        self.assertContains(
            response,
            'href="/securities/edinet_code_upload/upload"',
        )
        fetch_report_doc_list.assert_not_called()

    @patch("securities.views.XbrlService.fetch_report_doc_list", return_value=[])
    def test_post_with_company_shows_empty_result_message(self, fetch_report_doc_list):
        """
        シナリオ:
        - Given: 会社マスタがあり、指定期間に対象書類がない。
        - When: STEP 2で書類一覧の取得を実行する。
        - Then: STEP 1未実施案内ではなく、対象書類がないことを表示する。
        """
        Company.objects.create(edinet_code="E00001")

        response = self.client.post(
            "/securities/",
            {"start_date": "2026-06-01", "end_date": "2026-06-30"},
            follow=True,
        )

        self.assertContains(response, "指定した期間に対象書類はありません。")
        self.assertNotContains(response, "STEP 1の実施が必要です。")
        fetch_report_doc_list.assert_called_once()

    @patch("securities.views.XbrlService.fetch_report_doc_list")
    def test_post_with_company_saves_fetched_documents(self, fetch_report_doc_list):
        """
        シナリオ:
        - Given: 会社マスタがあり、取得サービスが書類を返す。
        - When: STEP 2で書類一覧の取得を実行する。
        - Then: 書類を保存し、書類一覧へリダイレクトする。
        """
        company = Company.objects.create(edinet_code="E00001")
        fetch_report_doc_list.return_value = [
            ReportDocument(
                seq_number=1,
                doc_id="S1000002",
                ordinance_code="010",
                form_code="030000",
                period_start=date(2026, 1, 1),
                period_end=date(2026, 3, 31),
                submit_date_time=datetime(2026, 6, 30, 9, 0, tzinfo=UTC),
                doc_description="有価証券報告書",
                withdrawal_status="0",
                doc_info_edit_status="0",
                disclosure_status="0",
                xbrl_flag=True,
                pdf_flag=True,
                english_doc_flag=False,
                csv_flag=False,
                legal_status=False,
                company=company,
            )
        ]

        response = self.client.post(
            "/securities/",
            {"start_date": "2026-06-01", "end_date": "2026-06-30"},
            follow=True,
        )

        self.assertContains(response, "S1000002")
        self.assertTrue(ReportDocument.objects.filter(doc_id="S1000002").exists())
        fetch_report_doc_list.assert_called_once()


class CompanyListViewTests(TestCase):
    def test_company_list_shows_fiscal_year_and_created_at(self):
        """
        Scenario:
        - Given: A company has a fiscal year end imported from the EDINET code list.
        - When: The company list is requested.
        - Then: The submitter, EDINET code, fiscal year end, and creation time are shown.
        """
        company = Company.objects.create(
            edinet_code="E00001",
            submitter_name="テスト株式会社",
            end_fiscal_year="3月31日",
        )

        response = self.client.get("/securities/companies/")

        self.assertContains(response, company.submitter_name)
        self.assertContains(response, company.edinet_code)
        self.assertContains(
            response,
            'href="https://disclosure2.edinet-fsa.go.jp/WEEK0010.aspx?bForm=true"',
        )
        self.assertContains(response, company.end_fiscal_year)
        self.assertContains(response, "確認日時")
        self.assertContains(response, company.created_at.strftime("%Y年"))

    def test_company_list_includes_incremental_search_data(self):
        """
        Scenario:
        - Given: A company has a submitter name and EDINET code.
        - When: The company list is requested.
        - Then: The incremental search input and row data are rendered.
        """
        Company.objects.create(
            edinet_code="E00003",
            submitter_name="検索対象株式会社",
            end_fiscal_year="12月31日",
        )

        response = self.client.get("/securities/companies/")

        self.assertContains(response, 'id="company-search"')
        self.assertContains(response, 'data-submitter-name="検索対象株式会社"')
        self.assertContains(response, 'data-edinet-code="E00003"')
        self.assertContains(response, "一致する企業はありません")

    def test_company_list_distinguishes_missing_fiscal_year(self):
        """
        Scenario:
        - Given: A company has no fiscal year end in the imported data.
        - When: The company list is requested.
        - Then: The missing value and the way to confirm it are shown separately.
        """
        Company.objects.create(edinet_code="E00002", submitter_name="未取得株式会社")

        response = self.client.get("/securities/companies/")

        self.assertContains(response, '<td class="text-center">-</td>', html=True)
        self.assertContains(
            response,
            "同じリストを再取込しても補完されません",
        )


class EdinetCodeImportCommandTests(TestCase):
    @staticmethod
    def _dataframe(end_fiscal_year="3月31日"):
        return pd.DataFrame(
            [
                {
                    "ＥＤＩＮＥＴコード": "E00001",
                    "提出者種別": "内国法人・組合",
                    "上場区分": "上場",
                    "連結の有無": "有",
                    "資本金": 100000,
                    "決算日": end_fiscal_year,
                    "提出者名": "テスト株式会社",
                    "提出者名（英字）": "Test Inc.",
                    "提出者名（ヨミ）": "テスト",
                    "所在地": "東京都",
                    "提出者業種": "サービス業",
                    "証券コード": "12345",
                    "提出者法人番号": "1234567890123",
                }
            ]
        )

    def test_import_records_fiscal_year_and_created_at(self):
        """
        Scenario:
        - Given: An EDINET code list contains a fiscal year end.
        - When: The import command is executed.
        - Then: The company stores the value and creation time.
        """
        with TemporaryDirectory() as directory:
            csv_path = Path(directory) / "EdinetcodeDlInfo.csv"
            csv_path.touch()
            with patch(
                "securities.management.commands.import_edinet_code.pd.read_csv",
                return_value=self._dataframe(),
            ):
                management.call_command("import_edinet_code", directory)

        company = Company.objects.get(edinet_code="E00001")

        self.assertEqual(company.end_fiscal_year, "3月31日")
        self.assertIsNotNone(company.created_at)

    def test_import_records_created_at_when_fiscal_year_is_missing(self):
        """
        Scenario:
        - Given: An EDINET code list has a company with no fiscal year end.
        - When: The import command is executed.
        - Then: The missing value still records the company creation time.
        """
        with TemporaryDirectory() as directory:
            csv_path = Path(directory) / "EdinetcodeDlInfo.csv"
            csv_path.touch()
            with patch(
                "securities.management.commands.import_edinet_code.pd.read_csv",
                return_value=self._dataframe(end_fiscal_year=None),
            ):
                management.call_command("import_edinet_code", directory)

        company = Company.objects.get(edinet_code="E00001")

        self.assertIsNone(company.end_fiscal_year)
        self.assertIsNotNone(company.created_at)

    def test_import_does_not_delete_existing_companies_when_fiscal_year_is_missing(
        self,
    ):
        """
        Scenario:
        - Given: An existing company is stored and a CSV has no fiscal year column.
        - When: The import command is executed.
        - Then: The command explains the failure and keeps the existing company.
        """
        existing_company = Company.objects.create(edinet_code="E99999")
        incomplete_data = self._dataframe().drop(columns=["決算日"])

        with TemporaryDirectory() as directory:
            csv_path = Path(directory) / "EdinetcodeDlInfo.csv"
            csv_path.touch()
            with patch(
                "securities.management.commands.import_edinet_code.pd.read_csv",
                return_value=incomplete_data,
            ):
                with self.assertRaises(CommandError) as error:
                    management.call_command("import_edinet_code", directory)

        self.assertIn("決算日がありません", str(error.exception))
        self.assertTrue(Company.objects.filter(pk=existing_company.pk).exists())
