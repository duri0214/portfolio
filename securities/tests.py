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


class CompanyListViewTests(TestCase):
    def test_company_list_shows_fiscal_year_source_and_checked_at(self):
        """
        Scenario:
        - Given: A company has a fiscal year end imported from the EDINET code list.
        - When: The company list is requested.
        - Then: The submitter, EDINET code, fiscal year end, source, and check time are shown.
        """
        company = Company.objects.create(
            edinet_code="E00001",
            submitter_name="テスト株式会社",
            end_fiscal_year="3月31日",
            fiscal_year_end_source="EDINETコードリストの決算日",
            fiscal_year_end_checked_at=datetime(2026, 10, 1, 9, 30, tzinfo=UTC),
        )

        response = self.client.get("/securities/companies/")

        self.assertContains(response, company.submitter_name)
        self.assertContains(response, company.edinet_code)
        self.assertContains(response, company.end_fiscal_year)
        self.assertContains(response, company.fiscal_year_end_source)
        self.assertContains(response, "2026年10月1日 18:30")

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
        self.assertContains(response, "EDINETコードリストの決算日")


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

    def test_import_records_fiscal_year_source_and_check_time(self):
        """
        Scenario:
        - Given: An EDINET code list contains a fiscal year end.
        - When: The import command is executed.
        - Then: The company stores the value, source, and import check time.
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
        self.assertEqual(company.fiscal_year_end_source, "EDINETコードリストの決算日")
        self.assertIsNotNone(company.fiscal_year_end_checked_at)

    def test_import_records_source_and_check_time_when_fiscal_year_is_missing(self):
        """
        Scenario:
        - Given: An EDINET code list has a company with no fiscal year end.
        - When: The import command is executed.
        - Then: The missing value still records its source and confirmation time.
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
        self.assertEqual(company.fiscal_year_end_source, "EDINETコードリストの決算日")
        self.assertIsNotNone(company.fiscal_year_end_checked_at)

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
