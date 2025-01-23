from unittest.mock import MagicMock, patch

from django.contrib.auth.models import User
from django.test import TestCase

from lib.llm.llm_service import OpenAIBatchCompletionService
from lib.llm.llm_service import (
    count_tokens,
    cut_down_chat_history,
)
from lib.llm.valueobject.chat import RoleType, Message, MessageChunk
from lib.llm.valueobject.config import OpenAIGptConfig
from lib.llm.valueobject.config import (
    validate_temperature,
)
from llm_chat.domain.valueobject.chat import MessageDTO


class TestLlmService(TestCase):
    def setUp(self):
        test_user, created = User.objects.get_or_create(
            username="test-user",
            defaults={"email": "test@example.com", "password": "test-password"},
        )
        if created:
            test_user.set_password("test-password")

        self.chat_history = [
            MessageDTO(
                content="Hello",
                role=RoleType.USER,
                invisible=False,
                user=test_user,
            ),
            MessageDTO(
                content=", ",
                role=RoleType.ASSISTANT,
                invisible=False,
                user=test_user,
            ),
            MessageDTO(
                content="world!",
                role=RoleType.USER,
                invisible=False,
                user=test_user,
            ),
        ]

    def test_count_tokens(self):
        token_count = count_tokens("こんにちは、世界!")
        self.assertIsInstance(token_count, int, "token_count は整数であるはずです")
        self.assertGreater(token_count, 0, "token_count は0より大きいはずです")

        token_count_empty = count_tokens("")
        self.assertEqual(token_count_empty, 0, "token_count は0であるはずです")

    def test_cut_down_chat_history(self):
        config = OpenAIGptConfig(
            api_key="xxx", max_tokens=100, model="gpt-4o-mini", temperature=0.5
        )
        cut_history = cut_down_chat_history(self.chat_history, config)
        self.assertIsInstance(cut_history, list, "cut_history はリストであるはずです")
        self.assertEqual(len(cut_history), 3, "すべてのメッセージが残るべきです")

    def test_cut_down_chat_history_with_less_max_tokens(self):
        config = OpenAIGptConfig(
            api_key="xxx", max_tokens=2, model="gpt-4o-mini", temperature=0.5
        )
        cut_history = cut_down_chat_history(self.chat_history, config)
        self.assertEqual(len(cut_history), 1, "最新のメッセージだけが残るべきです")
        self.assertEqual(cut_history[0].content, "world!", "メッセージ内容が正しいこと")

    def test_cut_down_chat_history_empty(self):
        config = OpenAIGptConfig(
            api_key="xxx", max_tokens=100, model="gpt-4o-mini", temperature=0.5
        )
        cut_history = cut_down_chat_history([], config)
        self.assertEqual(cut_history, [], "空のリストであるはずです")


class TestValidateTemperature(TestCase):
    def test_valid_temperature(self):
        # Test that valid temperatures do not raise error
        for temp in [0, 0.5, 1]:
            result = validate_temperature(temp)
            self.assertEqual(result, temp)

    def test_invalid_temperature(self):
        # Test that temperatures out of range raise ValueError
        for temp in [-1, 1.5]:
            with self.assertRaises(ValueError):
                validate_temperature(temp)


class TestOpenAIBatchCompletionService(TestCase):
    """OpenAIBatchCompletionServiceのテスト"""

    def setUp(self):
        """テストのセットアップ"""
        # テスト用のMessageChunkを作成
        self.sample_chunks = [
            MessageChunk(
                messages=[
                    Message(
                        role=RoleType.SYSTEM, content="You are a helpful assistant1."
                    ),
                    Message(role=RoleType.USER, content="What is your name?"),
                ],
                model="gpt-3.5-turbo",
                max_tokens=800,
            ),
            MessageChunk(
                messages=[
                    Message(
                        role=RoleType.SYSTEM, content="You are a helpful assistant2."
                    ),
                    Message(role=RoleType.USER, content="Tell me a joke."),
                ],
                model="gpt-3.5-turbo",
                max_tokens=800,
            ),
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
