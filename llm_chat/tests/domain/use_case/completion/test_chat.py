from django.test import TestCase
from django.contrib.auth.models import User
from unittest.mock import patch, MagicMock
from lib.llm.valueobject.completion import RoleType
from lib.llm.valueobject.config import OpenAIGptConfig, ModelName
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.use_case import UseCaseType
from llm_chat.domain.service.completion.chat import ChatService
from llm_chat.domain.use_case.completion.chat import LlmChatUseCase
from llm_chat.models import ChatLogs


class ChatUseCaseTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="logic_user")

    def test_get_chat_history_normal(self):
        """
        [シナリオ: 通常チャット]
        1. 過去の履歴がない状態で、ユーザーメッセージ (use_case_type=UseCaseType.OPENAI_GPT) を受け取る
        2. get_chat_history() を実行
        3. 期待値: 履歴リストにユーザーメッセージのみが含まれ、use_case_type が UseCaseType.OPENAI_GPT であること
        """
        user_message = MessageDTO(
            user=self.user,
            role=RoleType.USER,
            content="Normal message",
            model_name=ModelName.GPT_4O,
            use_case_type=UseCaseType.OPENAI_GPT,
        )
        history = ChatService.get_chat_history(
            user_message, use_case_type=UseCaseType.OPENAI_GPT
        )
        # 履歴が空なので、user_messageのみが保存される
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].content, "Normal message")
        self.assertEqual(history[0].use_case_type, UseCaseType.OPENAI_GPT)

    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_llm_chat_use_case_normal(self, mock_retrieve):
        """
        [シナリオ: 通常チャットユースケース]
        1. LlmChatUseCase を使用してユーザーメッセージを送信
        2. 期待値:
           - LLM の回答内容が正しく取得されること
           - 使用モデル名が設定値と一致すること
           - use_case_type が UseCaseType.OPENAI_GPT であること
           - ユーザーとアシスタントの計2通が DB に保存されること
        """
        mock_retrieve.return_value = MagicMock(answer="AIの回答です")
        config = OpenAIGptConfig(
            api_key="fake", max_tokens=100, model=ModelName.GPT_5_MINI
        )
        use_case = LlmChatUseCase(config)
        result = use_case.execute(self.user, "こんにちは")

        self.assertEqual(result.content, "AIの回答です")
        self.assertEqual(result.model_name, ModelName.GPT_5_MINI)
        self.assertEqual(result.use_case_type, UseCaseType.OPENAI_GPT)
        self.assertEqual(
            ChatLogs.objects.filter(user=self.user).count(), 2
        )  # User + Assistant
