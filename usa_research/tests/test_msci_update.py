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
    def test_scenario_1_initial_run(
        self, mock_llm_service, mock_pdf_reader, mock_requests_get, mock_requests_head
    ):
        """
        シナリオ1: 初回実行（DB空状態）
        - DBにレコードが1件もない状態でコマンドを実行。
        - HTTPヘッダの Last-Modified から抽出された日付で新規レコードが作成されることを確認。
        """
        # Setup mocks
        mock_requests_head.return_value = MagicMock(
            status_code=200, headers={"Last-Modified": "Wed, 01 May 2024 10:00:00 GMT"}
        )

        mock_response = MagicMock()
        mock_response.content = b"fake pdf content"
        mock_requests_get.return_value = mock_response

        mock_reader_inst = MagicMock()
        mock_reader_inst.pages = [MagicMock()]
        mock_reader_inst.pages[0].extract_text.return_value = "MSCI Report Content"
        mock_pdf_reader.return_value = mock_reader_inst

        mock_llm_inst = mock_llm_service.return_value
        mock_completion = MagicMock()
        mock_completion.answer = "Summary Content"
        mock_llm_inst.retrieve_answer.return_value = mock_completion

        # Execute command
        call_command("daily_update_msci_weights", url=self.pdf_url, stdout=self.out)

        # Verify record created
        self.assertEqual(MsciCountryWeightReport.objects.count(), 1)
        record = MsciCountryWeightReport.objects.first()
        self.assertEqual(record.report_date, datetime.date(2024, 5, 1))
        self.assertIn("Successfully processed", self.out.getvalue())

    @patch("usa_research.management.commands.daily_update_msci_weights.requests.head")
    @patch("usa_research.management.commands.daily_update_msci_weights.requests.get")
    @patch("usa_research.management.commands.daily_update_msci_weights.PdfReader")
    @patch(
        "usa_research.management.commands.daily_update_msci_weights.LlmCompletionService"
    )
    @patch.dict("os.environ", {"OPENAI_API_KEY": "fake_key"})
    def test_scenario_2_skip_by_head(
        self,
        mock_llm_service,
        mock_pdf_reader,
        mock_requests_get,
        mock_requests_head,
    ):
        """
        シナリオ2: HTTP HEADによる判定（更新なし）
        - PDFダウンロード前にヘッダの日付だけでスキップを判断する。
        - 通信量とLLMコストを最小限に抑える最速フロー。
        """
        latest_date = datetime.date(2026, 4, 3)
        MsciCountryWeightReport.objects.create(
            report_date=latest_date, summary_md="Latest summary", pdf_url=self.pdf_url
        )

        # HEADリクエストで返ってくる日付が DBと同じ (更新なし) の場合
        mock_requests_head.return_value = MagicMock(
            status_code=200,
            headers={"Last-Modified": "Fri, 03 Apr 2026 11:43:06 GMT"},
        )

        # Execute command
        call_command("daily_update_msci_weights", url=self.pdf_url, stdout=self.out)

        # 検証：ダウンロードやLLM解析が走っていないこと
        self.assertEqual(MsciCountryWeightReport.objects.count(), 1)
        self.assertIn("no update since", self.out.getvalue())
        mock_requests_get.assert_not_called()
        mock_llm_service.assert_not_called()

    @patch("usa_research.management.commands.daily_update_msci_weights.requests.head")
    @patch("usa_research.management.commands.daily_update_msci_weights.requests.get")
    @patch("usa_research.management.commands.daily_update_msci_weights.PdfReader")
    @patch(
        "usa_research.management.commands.daily_update_msci_weights.LlmCompletionService"
    )
    @patch.dict("os.environ", {"OPENAI_API_KEY": "fake_key"})
    def test_scenario_3_update_flow(
        self, mock_llm_service, mock_pdf_reader, mock_requests_get, mock_requests_head
    ):
        """
        シナリオ3: 新規データの更新
        - DBの最新より新しい日付のデータが来た場合に、正常に保存されることを確認。
        """
        # 古いデータがある
        old_date = datetime.date(2024, 4, 1)
        MsciCountryWeightReport.objects.create(
            report_date=old_date, summary_md="Old summary", pdf_url=self.pdf_url
        )

        # 新しい日付
        new_date = datetime.date(2024, 5, 1)
        mock_requests_head.return_value = MagicMock(
            status_code=200, headers={"Last-Modified": "Wed, 01 May 2024 10:00:00 GMT"}
        )

        mock_response = MagicMock()
        mock_response.content = b"fake pdf content"
        mock_requests_get.return_value = mock_response

        mock_reader_inst = MagicMock()
        mock_reader_inst.pages = [MagicMock()]
        mock_pdf_reader.return_value = mock_reader_inst

        mock_llm_inst = mock_llm_service.return_value
        mock_completion = MagicMock()
        mock_completion.answer = "New Summary"
        mock_llm_inst.retrieve_answer.return_value = mock_completion

        # Execute command
        call_command("daily_update_msci_weights", url=self.pdf_url, stdout=self.out)

        # 検証
        self.assertEqual(MsciCountryWeightReport.objects.count(), 2)
        latest = MsciCountryWeightReport.objects.order_by("-report_date").first()
        self.assertEqual(latest.report_date, new_date)
        self.assertIn(f"processed report for {new_date}", self.out.getvalue())

    @patch("usa_research.management.commands.daily_update_msci_weights.requests.head")
    @patch("usa_research.management.commands.daily_update_msci_weights.requests.get")
    @patch("usa_research.management.commands.daily_update_msci_weights.PdfReader")
    @patch(
        "usa_research.management.commands.daily_update_msci_weights.LlmCompletionService"
    )
    @patch.dict("os.environ", {"OPENAI_API_KEY": "fake_key"})
    def test_scenario_4_fallback_to_get_header(
        self,
        mock_llm_service,
        mock_pdf_reader,
        mock_requests_get,
        mock_requests_head,
    ):
        """
        シナリオ4: フォールバック（HEAD失敗時にGETのヘッダで判定）
        - HEADリクエストが失敗しても、GETリクエストのヘッダから日付を特定して処理を継続する。
        """
        # HEADは失敗させる
        mock_requests_head.side_effect = Exception("HEAD Fail")

        # GETリクエストのヘッダで日付を返す
        new_date = datetime.date(2024, 6, 1)
        mock_response = MagicMock()
        mock_response.content = b"fake pdf content"
        mock_response.status_code = 200
        mock_response.headers = {"Last-Modified": "Sat, 01 Jun 2024 10:00:00 GMT"}
        mock_requests_get.return_value = mock_response

        mock_reader_inst = MagicMock()
        mock_reader_inst.pages = [MagicMock()]
        mock_pdf_reader.return_value = mock_reader_inst

        mock_llm_inst = mock_llm_service.return_value
        mock_completion = MagicMock()
        mock_completion.answer = "Fallback Summary"
        mock_llm_inst.retrieve_answer.return_value = mock_completion

        # Execute command
        call_command("daily_update_msci_weights", url=self.pdf_url, stdout=self.out)

        # 検証
        self.assertEqual(MsciCountryWeightReport.objects.count(), 1)
        self.assertEqual(MsciCountryWeightReport.objects.first().report_date, new_date)
