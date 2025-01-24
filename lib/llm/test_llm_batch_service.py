from unittest.mock import MagicMock, patch

from django.test import TestCase

from lib.llm.llm_batch_service import OpenAIBatchCompletionService
from lib.llm.valueobject.chat import RoleType, Message
from lib.llm.valueobject.config import OpenAIGptConfig


class TestOpenAIBatchCompletionService(TestCase):
    """OpenAIBatchCompletionServiceのテスト"""

    def setUp(self):
        """テストのセットアップ"""
        self.sample_messages = [
            Message(role=RoleType.SYSTEM, content="You are a helpful assistant."),
            Message(role=RoleType.USER, content="What is your name?"),
        ]

        # Mock Config
        self.mock_config = OpenAIGptConfig(
            api_key="fake-api-key", model="gpt-4o", max_tokens=1000, temperature=0.7
        )

        # サービスを初期化
        self.service = OpenAIBatchCompletionService(config=self.mock_config)

    @patch("lib.llm.llm_service.OpenAI")  # OpenAIをモック
    @patch("lib.llm.llm_service.os.remove")  # 一時ファイル削除のモック
    @patch("lib.llm.llm_service.open", create=True)  # ファイル操作のモック
    def test_full_batch_process(self, mock_open, mock_os_remove, mock_openai):
        """
        OpenAIBatchCompletionServiceの一連の処理をテストする:
        - JSONLファイルのアップロード
        - バッチ作成
        - バッチのステータス確認
        """

        # OpenAI モック設定
        mock_openai_instance = mock_openai.return_value

        # ファイルアップロード用のモック戻り値
        mock_file_create_response = MagicMock()
        mock_file_create_response.id = "mock-file-id"
        mock_openai_instance.files.create.return_value = mock_file_create_response

        # バッチ作成モック戻り値
        mock_openai_instance.batches.create.return_value = MagicMock(
            id="mock-batch-id", status="in_progress"
        )

        # ステータス確認用ポーリングのモック戻り値
        mock_openai_instance.batches.retrieve.side_effect = [
            MagicMock(id="mock-batch-id", status="in_progress"),  # 初回のポーリング
            MagicMock(id="mock-batch-id", status="in_progress"),  # 次回のポーリング
            MagicMock(id="mock-batch-id", status="completed"),  # 完了ステータス
        ]

        # open モックの設定
        mock_file = MagicMock()
        mock_open.return_value.__enter__.return_value = (
            mock_file  # open時の返り値（ファイル）
        )

        # メソッドの実行
        file_id = self.service.upload_jsonl_file(
            self.sample_chunks
        )  # ファイルアップロード
        self.assertEqual(file_id, "mock-file-id")  # ファイルIDの確認

        batch = self.service.create_batch(file_id)  # バッチ作成
        self.assertEqual(batch.id, "mock-batch-id")  # バッチIDの確認

        # 実際にポーリングを模倣
        polling_result = None
        while True:
            polling_result = self.service.retrieve_answer(batch.id)
            if polling_result.status == "completed":
                break

        # 結果の確認（最終ステータスが "completed"）
        self.assertEqual(polling_result.status, "completed")
        self.assertEqual(polling_result.id, "mock-batch-id")

        # モック確認
        mock_openai_instance.files.create.assert_called_once()  # ファイル作成1回
        mock_openai_instance.batches.create.assert_called_once_with(
            input_file_id="mock-file-id",
            endpoint="/v1/chat/completions",
            completion_window="24h",
        )  # バッチ作成
        self.assertEqual(
            mock_openai_instance.batches.retrieve.call_count, 3
        )  # retrieve_answerが3回呼ばれる
