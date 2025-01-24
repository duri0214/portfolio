from unittest.mock import MagicMock, patch

from django.test import TestCase

from lib.llm.llm_batch_service import OpenAIBatchCompletionService
from lib.llm.valueobject.chat import RoleType, Message
from lib.llm.valueobject.chat_batch import MessageChunk
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

    @patch("os.path.exists", return_value=True)
    @patch("os.remove")
    def test_remove_file_if_exists(self, mock_remove, mock_exists):
        """
        1. `os.path.exists` をモックして、アップロードした一時ファイルが存在することにします。
        2. `os.remove` をモックして、削除処理が呼び出されるか検証します。
        """
        # テスト対象メソッドの実行
        self.service.remove_file_if_exists("test_file.jsonl")

        # 結果確認
        mock_exists.assert_called_once_with("test_file.jsonl")
        mock_remove.assert_called_once_with("test_file.jsonl")

    def test_parse_to_message_chunk(self):
        """parse_to_message_chunkのテスト"""
        # メソッドの実行
        result_chunk = self.service.parse_to_message_chunk(self.sample_messages)

        # 結果の確認
        self.assertIsInstance(
            result_chunk, MessageChunk, "戻り値がMessageChunkであるべき"
        )
        self.assertEqual(
            result_chunk.messages,
            self.sample_messages,
            "結果のメッセージリストが一致するべき",
        )
        self.assertEqual(result_chunk.model, "gpt-4o", "モデル名が設定されるべき")
        self.assertEqual(result_chunk.max_tokens, 1000, "max_tokensが設定されるべき")

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

    @patch("lib.llm.llm_batch_service.OpenAI")
    @patch("lib.llm.llm_batch_service.OpenAIBatchCompletionService.export_jsonl_file")
    @patch("builtins.open", new_callable=MagicMock)
    def test_file_delete_with_upload_jsonl(
        self,
        mock_open,
        mock_export_jsonl_file,
        mock_openai,
    ):
        """
        upload_jsonl_fileメソッドをテストする。

        テストの流れ:
        1. `export_jsonl_file` をモックし、jsonlファイルを作ったことにします。
        2. `open` をモックして、実際にファイルを操作せずとも、ファイルを開いたことにします。
        3. `OpenAI` ライブラリの `files.create` メソッドをモックし、アップロードしたことにします。

        確認事項:
        - upload_jsonl_fileにより返されるファイルIDが "mock-file-id" であること。
        """
        # モックされた `export_jsonl_file` の設定
        mock_export_jsonl_file.return_value = "mock_file.jsonl"

        # モックされた `open` の設定
        mock_open.return_value.__enter__.return_value = MagicMock()

        # モックされた `OpenAI` の設定
        mock_openai_instance = mock_openai.return_value
        mock_file_create_response = MagicMock()
        mock_file_create_response.id = "mock-file-id"
        mock_openai_instance.files.create.return_value = mock_file_create_response

        # テスト対象メソッドの実行
        file_id = self.service.upload_jsonl_file(
            [
                MessageChunk(
                    messages=self.sample_messages,
                    model=self.mock_config.model,
                    max_tokens=self.mock_config.max_tokens,
                )
            ]
        )

        # upload_jsonl_fileの結果確認
        self.assertEqual(file_id, "mock-file-id", "ファイルIDが正しいこと")
