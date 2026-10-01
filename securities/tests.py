from datetime import UTC, date, datetime

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
