import datetime
from io import StringIO
from unittest.mock import patch, MagicMock

from django.core.management import call_command
from django.test import TestCase

from usa_research.models import MsciCountryWeightReport


class MsciUpdateIdempotencyTest(TestCase):
    """
    MSCIレポート更新コマンドの堅牢性を検証するテストクラス。
    日次バッチ実行を想定し、データの重複登録防止（冪等性）や
    初回実行時の挙動をシナリオベースで確認する。
    """

    def setUp(self):
        self.out = StringIO()
        self.pdf_url = "https://example.com/msci.pdf"

    @patch("usa_research.management.commands.daily_update_msci_weights.requests.head")
    @patch("usa_research.management.commands.daily_update_msci_weights.requests.get")
    @patch("usa_research.management.commands.daily_update_msci_weights.PdfReader")
    @patch(
        "usa_research.management.commands.daily_update_msci_weights.LlmCompletionService"
    )
    @patch.dict("os.environ", {"OPENAI_API_KEY": "fake_key"})
    def test_initial_run(
        self, mock_llm_service, mock_pdf_reader, mock_requests_get, mock_requests_head
    ):
        """
        シナリオ1: 初回実行（DB空状態）
        - DBにレコードが1件もない状態でコマンドを実行する。
        - PDFから抽出された日付で新規レコードが作成されることを確認する。
        """
        # Setup mocks
        mock_requests_head.return_value = MagicMock(status_code=200, headers={})

        mock_response = MagicMock()
        mock_response.content = b"fake pdf content"
        mock_requests_get.return_value = mock_response

        mock_reader_inst = MagicMock()
        mock_reader_inst.pages = [MagicMock()]
        mock_reader_inst.pages[0].extract_text.return_value = "MSCI Report Content"
        mock_pdf_reader.return_value = mock_reader_inst

        mock_llm_inst = mock_llm_service.return_value
        mock_completion = MagicMock()
        mock_completion.answer = "Report Date: 2024-05-01\n\nSummary Content"
        mock_llm_inst.retrieve_answer.return_value = mock_completion

        # Execute command
        call_command("daily_update_msci_weights", url=self.pdf_url, stdout=self.out)

        # Verify record created
        self.assertEqual(MsciCountryWeightReport.objects.count(), 1)
        record = MsciCountryWeightReport.objects.first()
        self.assertEqual(record.report_date, datetime.date(2024, 5, 1))
        self.assertIn("Successfully processed", self.out.getvalue())
        self.assertIn("Initial data migration", self.out.getvalue())

    @patch("usa_research.management.commands.daily_update_msci_weights.requests.head")
    @patch("usa_research.management.commands.daily_update_msci_weights.requests.get")
    @patch("usa_research.management.commands.daily_update_msci_weights.PdfReader")
    @patch(
        "usa_research.management.commands.daily_update_msci_weights.LlmCompletionService"
    )
    @patch.dict("os.environ", {"OPENAI_API_KEY": "fake_key"})
    def test_idempotency_same_date(
        self,
        mock_llm_service,
        mock_pdf_reader,
        mock_requests_get,
        mock_requests_head,
    ):
        """
        シナリオ2: 同一データによる重複実行（冪等性の担保）
        - 既に特定のReport Dateのレコードが存在する状態で、同じ日付のPDFを処理する。
        - 新規レコードは作成されず、既存データも上書きされない（スキップされる）ことを確認する。
        """
        # Create an existing record
        report_date = datetime.date(2024, 5, 1)
        MsciCountryWeightReport.objects.create(
            report_date=report_date, summary_md="Existing summary", pdf_url=self.pdf_url
        )

        # Setup mocks to return the same date in LLM (HEAD skip not triggered yet)
        mock_requests_head.return_value = MagicMock(status_code=200, headers={})

        mock_response = MagicMock()
        mock_response.content = b"fake pdf content"
        mock_requests_get.return_value = mock_response

        mock_reader_inst = MagicMock()
        mock_reader_inst.pages = [MagicMock()]
        mock_pdf_reader.return_value = mock_reader_inst

        mock_llm_inst = mock_llm_service.return_value
        mock_completion = MagicMock()
        mock_completion.answer = f"Report Date: {report_date}\n\nNew Summary Content"
        mock_llm_inst.retrieve_answer.return_value = mock_completion

        # Execute command
        call_command("daily_update_msci_weights", url=self.pdf_url, stdout=self.out)

        # Verify no new record created and no update (based on logic, it skips)
        self.assertEqual(MsciCountryWeightReport.objects.count(), 1)
        self.assertIn(f"Already updated for {report_date}", self.out.getvalue())

    @patch("usa_research.management.commands.daily_update_msci_weights.requests.head")
    @patch("usa_research.management.commands.daily_update_msci_weights.requests.get")
    @patch("usa_research.management.commands.daily_update_msci_weights.PdfReader")
    @patch(
        "usa_research.management.commands.daily_update_msci_weights.LlmCompletionService"
    )
    @patch.dict("os.environ", {"OPENAI_API_KEY": "fake_key"})
    def test_head_skip(
        self,
        mock_llm_service,
        mock_pdf_reader,
        mock_requests_get,
        mock_requests_head,
    ):
        """
        シナリオ5: HTTP HEADリクエストによる早期スキップ
        - HTTP HEADで取得した Last-Modified が、DBの最新レコードの日付以前であれば
        - PDFのダウンロードやLLM解析を行わずに終了することを確認する。
        """
        # 最新レコードが 2026-04-03
        latest_date = datetime.date(2026, 4, 3)
        MsciCountryWeightReport.objects.create(
            report_date=latest_date, summary_md="Latest summary", pdf_url=self.pdf_url
        )

        # HEADリクエストで返ってくる日付が 2026-04-03 (同日) の場合
        mock_requests_head.return_value = MagicMock(
            status_code=200,
            headers={"Last-Modified": "Fri, 03 Apr 2026 11:43:06 GMT"},
        )

        # Execute command
        call_command("daily_update_msci_weights", url=self.pdf_url, stdout=self.out)

        # 検証
        self.assertEqual(MsciCountryWeightReport.objects.count(), 1)
        self.assertIn("HTTP Head indicates no update", self.out.getvalue())
        # GETリクエストやLLMが呼ばれていないことを確認
        mock_requests_get.assert_not_called()
        mock_llm_service.assert_not_called()

    @patch("usa_research.management.commands.daily_update_msci_weights.requests.get")
    @patch("usa_research.management.commands.daily_update_msci_weights.PdfReader")
    @patch(
        "usa_research.management.commands.daily_update_msci_weights.LlmCompletionService"
    )
    @patch.dict("os.environ", {"OPENAI_API_KEY": "fake_key"})
    def test_new_date_update(
        self, mock_llm_service, mock_pdf_reader, mock_requests_get
    ):
        """
        シナリオ3: 新規データの更新
        - DBに古い日付のレコードが存在する状態で、より新しい日付のPDFを処理する。
        - 新しい日付のレコードが追加され、最新データとして保持されることを確認する。
        """
        # Create an existing record
        old_date = datetime.date(2024, 4, 1)
        MsciCountryWeightReport.objects.create(
            report_date=old_date, summary_md="Old summary", pdf_url=self.pdf_url
        )

        # Setup mocks to return a newer date
        new_date = datetime.date(2024, 5, 1)
        mock_response = MagicMock()
        mock_response.content = b"fake pdf content"
        mock_requests_get.return_value = mock_response

        mock_reader_inst = MagicMock()
        mock_reader_inst.pages = [MagicMock()]
        mock_reader_inst.pages[0].extract_text.return_value = "MSCI Report Content"
        mock_pdf_reader.return_value = mock_reader_inst

        mock_llm_inst = mock_llm_service.return_value
        mock_completion = MagicMock()
        mock_completion.answer = f"Report Date: {new_date}\n\nNew Summary"
        mock_llm_inst.retrieve_answer.return_value = mock_completion

        # Execute command
        call_command("daily_update_msci_weights", url=self.pdf_url, stdout=self.out)

        # Verify a new record created
        self.assertEqual(MsciCountryWeightReport.objects.count(), 2)
        latest = MsciCountryWeightReport.objects.order_by("-report_date").first()
        self.assertEqual(latest.report_date, new_date)
        self.assertIn(
            f"Successfully processed report for {new_date}", self.out.getvalue()
        )

    @patch("usa_research.management.commands.daily_update_msci_weights.requests.get")
    @patch("usa_research.management.commands.daily_update_msci_weights.PdfReader")
    @patch(
        "usa_research.management.commands.daily_update_msci_weights.LlmCompletionService"
    )
    @patch.dict("os.environ", {"OPENAI_API_KEY": "fake_key"})
    def test_old_date_skip(self, mock_llm_service, mock_pdf_reader, mock_requests_get):
        """
        シナリオ4: 過去データのスキップ（逆転防止）
        - 最新レコードよりも古い日付を持つPDFが提示された場合（例: キャッシュや古いURLなど）。
        - DBの最新性を守るため、処理がスキップされることを確認する。
        """
        # 最新レコードが 2024-05-01
        latest_date = datetime.date(2024, 5, 1)
        MsciCountryWeightReport.objects.create(
            report_date=latest_date, summary_md="Latest summary", pdf_url=self.pdf_url
        )

        # PDFから抽出された日付が過去（2024-04-01）の場合
        old_date = datetime.date(2024, 4, 1)
        mock_response = MagicMock()
        mock_response.content = b"fake pdf content"
        mock_requests_get.return_value = mock_response

        mock_reader_inst = MagicMock()
        mock_reader_inst.pages = [MagicMock()]
        mock_pdf_reader.return_value = mock_reader_inst

        mock_llm_inst = mock_llm_service.return_value
        mock_completion = MagicMock()
        mock_completion.answer = f"Report Date: {old_date}\n\nOld Summary"
        mock_llm_inst.retrieve_answer.return_value = mock_completion

        # コマンド実行
        call_command("daily_update_msci_weights", url=self.pdf_url, stdout=self.out)

        # レコードが増えていないこと、およびスキップメッセージを確認
        self.assertEqual(MsciCountryWeightReport.objects.count(), 1)
        self.assertIn(f"Already updated for {old_date}", self.out.getvalue())
