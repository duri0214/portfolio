from django.test import TestCase
from django.contrib.auth.models import User
from lib.llm.valueobject.completion import RoleType
from lib.llm.valueobject.config import OpenAIGptConfig, ModelName
from llm_chat.models import ChatLogs
from llm_chat.domain.valueobject.chat import MessageDTO, Gender, GenderType
from llm_chat.domain.repository.chat import ChatLogRepository
from llm_chat.domain.service.chat import (
    get_chat_history,
    RIDDLE_END_MESSAGE,
)
from llm_chat.domain.usecase.chat import LlmChatUseCase, RiddleUseCase
from unittest.mock import patch, MagicMock


class ChatModelAndRepositoryTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="testuser")

    def test_chat_logs_to_message_dto(self):
        """
        [シナリオ]
        1. ChatLogs エンティティを作成 (role='user', content='Hello', is_riddle=False)
        2. to_message_dto() を呼び出して MessageDTO に変換
        3. 期待値: 各フィールドが正しくマッピングされ、is_riddle が False であること
        """
        log = ChatLogs.objects.create(
            user=self.user,
            role=RoleType.USER.value,
            content="Hello",
            model_name=ModelName.GPT_5_MINI,
            is_riddle=False,
        )
        dto = log.to_message_dto()
        self.assertEqual(dto.content, "Hello")
        self.assertEqual(dto.model_name, ModelName.GPT_5_MINI)
        self.assertFalse(dto.is_riddle)

    def test_repository_insert_and_find(self):
        """
        [シナリオ]
        1. ユーザーメッセージを模した MessageDTO を作成 (role='assistant', is_riddle=True)
        2. ChatLogRepository.insert() を使用して DB に保存
        3. find_chat_history() でそのユーザーの履歴を取得
        4. 期待値: 取得した履歴が1件であり、内容と is_riddle フラグが一致すること
        """
        dto = MessageDTO(
            user=self.user,
            role=RoleType.ASSISTANT,
            content="AI response",
            model_name=ModelName.GPT_5_MINI,
            is_riddle=True,
        )
        ChatLogRepository.insert(dto)

        history = ChatLogRepository.find_chat_history(self.user)
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].content, "AI response")
        self.assertTrue(history[0].is_riddle)


class ChatLogicTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="logicuser")

    def test_get_chat_history_normal(self):
        """
        [シナリオ: 通常チャット]
        1. 過去の履歴がない状態で、ユーザーメッセージ (is_riddle=False) を受け取る
        2. get_chat_history() を実行
        3. 期待値: 履歴リストにユーザーメッセージのみが含まれ、is_riddle が False であること
        """
        user_message = MessageDTO(
            user=self.user,
            role=RoleType.USER,
            content="Normal message",
            model_name=ModelName.GPT_5_MINI,
            is_riddle=False,
        )
        history = get_chat_history(user_message, is_riddle=False)
        # 履歴が空なので、user_messageのみが保存される
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].content, "Normal message")
        self.assertFalse(history[0].is_riddle)

    def test_get_chat_history_riddle_first(self):
        """
        [シナリオ: なぞなぞ初回開始]
        1. 過去の履歴がない状態で、ユーザーメッセージ (is_riddle=True) を受け取る
        2. get_chat_history(is_riddle=True) を実行
        3. 期待値:
           - 内部的にシステムメッセージが生成され、履歴リストの先頭に追加されること (計2通)
           - ユーザーメッセージのみが DB に保存されること
        """
        user_message = MessageDTO(
            user=self.user,
            role=RoleType.USER,
            content="なぞなぞスタート",
            model_name=ModelName.GPT_5_MINI,
            is_riddle=True,
        )
        # 初回：システムメッセージ（非保存）と初回ユーザーメッセージ（保存）
        history = get_chat_history(
            user_message, is_riddle=True, gender=Gender(GenderType.MAN)
        )
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].role, RoleType.SYSTEM)
        self.assertEqual(history[1].role, RoleType.USER)
        self.assertTrue(history[1].is_riddle)

        # DBにはユーザーメッセージのみ保存されているはず
        db_logs = ChatLogs.objects.filter(user=self.user)
        self.assertEqual(db_logs.count(), 1)
        self.assertEqual(db_logs[0].role, RoleType.USER.value)

    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_riddle_use_case_end_detection(self, mock_retrieve):
        """
        [シナリオ: なぞなぞ終了判定]
        1. LLM の回答に終了キーワード (RIDDLE_END_MESSAGE) が含まれるケースを模倣
        2. RiddleUseCase.execute() を実行
        3. 期待値:
           - 回答内容に終了メッセージが含まれていること
           - 回答後の評価結果が含まれていること
           - メッセージの is_riddle フラグが True であること
        """
        # 終了メッセージを含む回答を模倣
        mock_retrieve.return_value = MagicMock(
            answer=f"正解です！ {RIDDLE_END_MESSAGE}"
        )

        config = OpenAIGptConfig(
            api_key="fake", max_tokens=100, model=ModelName.GPT_5_MINI
        )
        use_case = RiddleUseCase(config)

        # RiddleUseCase.execute は内部で evaluate を呼ぶ（さらに LLM 実行）
        # 簡単のため、evaluate もモック化するか、retrieve_answer を 2回返すように設定
        with patch("llm_chat.domain.service.chat.ChatService.evaluate") as mock_eval:
            mock_eval.return_value = "\n【評価結果】\n- 論理的思考力: 100点 (合格)"

            result = use_case.execute(self.user, "答えは人間です")

            self.assertIn(RIDDLE_END_MESSAGE, result.content)
            self.assertIn("評価結果", result.content)
            self.assertTrue(result.is_riddle)

    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_llm_chat_use_case_normal(self, mock_retrieve):
        """
        [シナリオ: 通常チャットユースケース]
        1. LlmChatUseCase を使用してユーザーメッセージを送信
        2. 期待値:
           - LLM の回答内容が正しく取得されること
           - 使用モデル名が設定値と一致すること
           - is_riddle フラグが False であること
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
        self.assertFalse(result.is_riddle)
        self.assertEqual(
            ChatLogs.objects.filter(user=self.user).count(), 2
        )  # User + Assistant

    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_riddle_use_case_normal(self, mock_retrieve):
        """
        [シナリオ: なぞなぞユースケース]
        1. RiddleUseCase を使用してなぞなぞを開始
        2. 期待値:
           - 回答内容が取得され、is_riddle フラグが True であること
           - ユーザーとアシスタントの計2通が DB に保存されること (システムメッセージは保存されない)
        """
        mock_retrieve.return_value = MagicMock(answer="それは人間ですか？")
        config = OpenAIGptConfig(
            api_key="fake", max_tokens=100, model=ModelName.GPT_5_MINI
        )
        use_case = RiddleUseCase(config)
        result = use_case.execute(self.user, "スタート")

        self.assertEqual(result.content, "それは人間ですか？")
        self.assertTrue(result.is_riddle)
        # 初回なぞなぞ：System(非保存), User, Assistant の計2通がDBへ
        self.assertEqual(ChatLogs.objects.filter(user=self.user).count(), 2)


class ViewLogicTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(
            username="admin", password="password", email="admin@example.com"
        )

    def test_index_view_riddle_active_status(self):
        """
        [シナリオ: Viewにおけるなぞなぞ活性状態判定]
        1. 履歴がない場合: is_riddle_active が False であることを確認
        2. 最新履歴がなぞなぞメッセージ (終了なし) の場合: is_riddle_active が True になることを確認
        3. 最新履歴になぞなぞ終了メッセージが含まれる場合: is_riddle_active が False に戻ることを確認
        """
        from django.test import RequestFactory
        from llm_chat.views import IndexView

        factory = RequestFactory()
        request = factory.get("/")
        request.user = self.user

        # 1. 履歴なし -> Riddle 非アクティブ
        view = IndexView()
        view.request = request
        context = view.get_context_data()
        self.assertFalse(context["is_riddle_active"])

        # 2. なぞなぞ開始メッセージあり -> Riddle アクティブ
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.ASSISTANT.value,
            content="なぞなぞを出題します",
            is_riddle=True,
        )
        context = view.get_context_data()
        self.assertTrue(context["is_riddle_active"])

        # 3. なぞなぞ終了メッセージあり -> Riddle 非アクティブ
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.ASSISTANT.value,
            content=f"お疲れ様でした。 {RIDDLE_END_MESSAGE}",
            is_riddle=True,
        )
        context = view.get_context_data()
        self.assertFalse(context["is_riddle_active"])
