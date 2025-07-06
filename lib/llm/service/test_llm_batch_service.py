import json
import os
from unittest.mock import MagicMock, patch

from django.test import TestCase

from lib.llm.service.completion_batch import OpenAIBatchCompletionService
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
        self.assertIsInstance(result_chunk, MessageChunk)
        self.assertEqual(result_chunk.messages, self.sample_messages)
        self.assertEqual(result_chunk.model, "gpt-4o")
        self.assertEqual(result_chunk.max_tokens, 1000)

    def test_export_jsonl_file(self):
        """
        export_jsonl_fileが正しい内容のファイルを生成できることを確認するテスト。

        このテストでは、以下の事項を検証します:
        1. 指定されたMessageChunkリストがJSONL形式で正しくシリアライズされ、
           各行が1つのJSONオブジェクトとして保存されること。
        2. ファイルが意図した形式（JSONL）および行数で構成されていること。
        3. ファイル作成後、データが期待通りの内容であること（role、content の値が一致するか）。
        """
        # メソッド実行
        result_chunk = [self.service.parse_to_message_chunk(self.sample_messages)]
        file_path = self.service.export_jsonl_file(result_chunk)

        try:
            # ファイルが作成されたことを確認する
            self.assertTrue(os.path.exists(file_path))

            # ファイル内容を確認して行数が正しいことを確認する
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
            self.assertEqual(len(lines), len(result_chunk))

            # ファイル内容が意図した形式であること
            for line in lines:
                data = json.loads(line.strip())
                self.assertEqual(data["body"]["messages"][0]["role"], "system")
                self.assertEqual(
                    data["body"]["messages"][0]["content"],
                    "You are a helpful assistant.",
                )
        finally:
            self.service.remove_file_if_exists(file_path)

    @patch(
        "lib.llm.service.completion_batch.OpenAIBatchCompletionService.remove_file_if_exists"
    )
    @patch("lib.llm.service.completion_batch.OpenAIBatchCompletionService.export_jsonl_file")
    @patch("builtins.open", new_callable=MagicMock)
    @patch("lib.llm.service.completion_batch.OpenAI")
    def test_upload_jsonl_file(
        self,
        mock_openai,
        mock_open,
        mock_export_jsonl_file,
        mock_remove_file_if_exists,
    ):
        """
        upload_jsonl_fileメソッドをテストする。

        このテストでは:
        1. `export_jsonl_file` をモックし、jsonlファイルを作ったことにします。
        2. `open` をモックして、実際にファイルを操作せずとも、ファイルを開いたことにします。
        3. `OpenAI` ライブラリの `files.create` メソッドをモックし、アップロードしたことにします。
        4. ファイル削除処理が呼び出されること（`remove_file_if_exists`をテスト済である前提）。
        """
        # モックされた `export_jsonl_file` の設定
        mock_export_jsonl_file.return_value = "mock_file.jsonl"

        # モックされた `open` の設定
        mock_open.return_value.__enter__.return_value = MagicMock()

        # モックされた `OpenAI` の設定
        mock_openai_instance = mock_openai.return_value
        mock_file_create_response = MagicMock(id="mock-file-id")
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

        # export_jsonl_file が1度だけ呼ばれるか確認
        mock_export_jsonl_file.assert_called_once()
        # ファイルアップロードが1回のみされるか確認
        mock_openai_instance.files.create.assert_called_once()
        # ファイルIDの確認
        self.assertEqual(file_id, "mock-file-id", "ファイルIDが正しいこと")
        # 削除処理呼び出し が1度だけ呼ばれるか確認
        mock_remove_file_if_exists.assert_called_once_with("mock_file.jsonl")
