from django.test import TestCase
from django.contrib.auth.models import User
from lib.llm.valueobject.completion import RoleType
from lib.llm.valueobject.config import ModelName
from llm_chat.models import ChatLogs
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.use_case import UseCaseType
from llm_chat.domain.repository.completion.chat import ChatLogRepository


class ChatModelAndRepositoryTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="test_user")

    def test_chat_logs_to_message_dto(self):
        """
        [シナリオ]
        1. ChatLogs エンティティを作成 (role='user', content='Hello', use_case_type=UseCaseType.OPENAI_GPT)
        2. to_message_dto() を呼び出して MessageDTO に変換
        3. 期待値: 各フィールドが正しくマッピングされ、use_case_type が UseCaseType.OPENAI_GPT であること
        """
        log = ChatLogs.objects.create(
            user=self.user,
            role=RoleType.USER.value,
            content="Hello",
            model_name=ModelName.GPT_4O,
        )
        dto = log.to_message_dto()
        self.assertEqual(dto.content, "Hello")
        self.assertEqual(dto.model_name, ModelName.GPT_4O)
        self.assertEqual(dto.use_case_type, UseCaseType.OPENAI_GPT)

    def test_repository_insert_and_find(self):
        """
        [シナリオ]
        1. ユーザーメッセージを模した MessageDTO を作成 (role='assistant', use_case_type=UseCaseType.RIDDLE)
        2. ChatLogRepository.insert() を使用して DB に保存
        3. find_chat_history() でそのユーザーの履歴を取得
        4. 期待値: 取得した履歴が1件であり、内容と use_case_type が一致すること
        """
        dto = MessageDTO(
            user=self.user,
            role=RoleType.ASSISTANT,
            content="AI response",
            model_name=ModelName.GPT_4O,
            use_case_type=UseCaseType.RIDDLE,
        )
        ChatLogRepository.insert(dto)

        history = ChatLogRepository.find_chat_history(self.user)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].content, "AI response")
        self.assertEqual(history[0].use_case_type, UseCaseType.RIDDLE)
