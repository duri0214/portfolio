import time
from django.test import TestCase, RequestFactory
from django.contrib.sessions.backends.db import SessionStore
from django.contrib.auth.models import User
from lib.llm.valueobject.completion import RoleType
from lib.llm.valueobject.config import OpenAIGptConfig, ModelName
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from llm_chat.models import ChatLogs
from llm_chat.views import IndexView
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.riddle import Gender, GenderType
from llm_chat.domain.valueobject.completion.use_case import UseCaseType
from llm_chat.domain.repository.completion.chat import ChatLogRepository
from llm_chat.domain.service.completion.chat import ChatService
from llm_chat.domain.service.completion.riddle import RiddleChatService
from llm_chat.domain.usecase.completion.chat import LlmChatUseCase
from llm_chat.domain.usecase.completion.multimedia import (
    OpenAIDalleUseCase,
    OpenAITextToSpeechUseCase,
    OpenAISpeechToTextUseCase,
)
from llm_chat.domain.usecase.completion.riddle import RiddleUseCase
from unittest.mock import patch, MagicMock


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


class ChatLogicTest(TestCase):
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

    def test_get_chat_history_riddle_first(self):
        """
        [シナリオ: なぞなぞ初回開始]
        1. 過去の履歴がない状態で、ユーザーメッセージ (use_case_type=UseCaseType.RIDDLE) を受け取る
        2. get_chat_history(use_case_type=UseCaseType.RIDDLE) を実行
        3. 期待値:
           - 内部的にシステムメッセージが生成され、履歴リストの先頭に追加されること (計2通)
           - ユーザーメッセージのみが DB に保存されること
        """
        user_message = MessageDTO(
            user=self.user,
            role=RoleType.USER,
            content="なぞなぞスタート",
            model_name=ModelName.GPT_5_MINI,
            use_case_type=UseCaseType.RIDDLE,
        )
        # 初回：システムメッセージ（非保存）と初回ユーザーメッセージ（保存）
        history = ChatService.get_chat_history(
            user_message,
            use_case_type=UseCaseType.RIDDLE,
            gender=Gender(GenderType.MAN),
        )
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0].role, RoleType.SYSTEM)
        self.assertEqual(history[1].role, RoleType.USER)
        self.assertEqual(history[1].use_case_type, UseCaseType.RIDDLE)

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
           - メッセージの use_case_type が UseCaseType.RIDDLE であること
        """
        # 終了メッセージを含む回答を模倣
        mock_retrieve.return_value = MagicMock(
            answer=f"正解です！ {RiddleChatService.RIDDLE_END_MESSAGE}"
        )

        config = OpenAIGptConfig(
            api_key="fake", max_tokens=100, model=ModelName.GPT_5_MINI
        )
        use_case = RiddleUseCase(config)

        # RiddleUseCase.execute は内部で evaluate を呼ぶ（さらに LLM 実行）
        # 簡単のため、evaluate もモック化するか、retrieve_answer を 2回返すように設定
        with patch(
            "llm_chat.domain.service.completion.chat.ChatService.evaluate"
        ) as mock_eval:
            mock_eval.return_value = "\n【評価結果】\n- 論理的思考力: 100点 (合格)"

            result = use_case.execute(
                self.user, "答えは人間です", gender=Gender(GenderType.MAN)
            )

            self.assertIn(RiddleChatService.RIDDLE_END_MESSAGE, result.content)
            self.assertIn("評価結果", result.content)
            self.assertEqual(result.use_case_type, UseCaseType.RIDDLE)

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

    @patch("lib.llm.service.completion.LlmCompletionService.retrieve_answer")
    def test_riddle_use_case_normal(self, mock_retrieve):
        """
        [シナリオ: なぞなぞユースケース]
        1. RiddleUseCase を使用してなぞなぞを開始
        2. 期待値:
           - 回答内容が取得され、use_case_type が UseCaseType.RIDDLE であること
           - ユーザーとアシスタントの計2通が DB に保存されること (システムメッセージは保存されない)
        """
        mock_retrieve.return_value = MagicMock(answer="それは人間ですか？")
        config = OpenAIGptConfig(
            api_key="fake", max_tokens=100, model=ModelName.GPT_5_MINI
        )
        use_case = RiddleUseCase(config)
        result = use_case.execute(self.user, "スタート", gender=Gender(GenderType.MAN))

        self.assertEqual(result.content, "それは人間ですか？")
        self.assertEqual(result.use_case_type, UseCaseType.RIDDLE)
        # 初回なぞなぞ：System(非保存), User, Assistant の計2通がDBへ
        self.assertEqual(ChatLogs.objects.filter(user=self.user).count(), 2)

    def test_get_chat_history_riddle_no_gender_raises_error(self):
        """
        [シナリオ] なぞなぞモードで性別を指定せずに get_chat_history を呼び出す
        [期待値] ValueError が発生すること
        """
        user_message = MessageDTO(
            user=self.user,
            role=RoleType.USER,
            content="なぞなぞスタート",
            model_name=ModelName.GPT_5_MINI,
            use_case_type=UseCaseType.RIDDLE,
        )
        with self.assertRaisesRegex(ValueError, "gender is required for RiddleUseCase"):
            ChatService.get_chat_history(
                user_message, use_case_type=UseCaseType.RIDDLE, gender=None
            )

    def test_riddle_usecase_no_gender_raises_error(self):
        """
        [シナリオ] RiddleUseCase.execute を性別指定なしで呼び出す
        [期待値] ValueError が発生すること
        """
        config = OpenAIGptConfig(
            api_key="fake", max_tokens=100, model=ModelName.GPT_5_MINI
        )
        use_case = RiddleUseCase(config)
        with self.assertRaisesRegex(ValueError, "gender is required for RiddleUseCase"):
            use_case.execute(user=self.user, content="なぞなぞスタート", gender=None)


class OpenAiUseCaseTest(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="openai_user", password="password"
        )

    def _assert_chat_log_saved(self, model_name: ModelName, use_case_type: UseCaseType):
        """ChatLogs にファイルパスとモデル名、ユースケースタイプが正しく保存されていることを検証する共通ヘルパー"""
        last_log = ChatLogs.objects.filter(
            user=self.user, role=RoleType.ASSISTANT.value
        ).last()
        self.assertIsNotNone(last_log)
        self.assertIsNotNone(last_log.file.name)
        self.assertEqual(last_log.model_name, model_name)
        self.assertEqual(last_log.use_case_type, use_case_type)

    @patch("llm_chat.domain.service.completion.multimedia.OpenAILlmDalleService")
    @patch("llm_chat.domain.service.completion.multimedia.requests.get")
    @patch("llm_chat.domain.service.completion.multimedia.Image.open")
    def test_dalle_usecase_saves_file_path(
        self, mock_image_open, mock_get, mock_dalle_service
    ):
        """
        [シナリオ: DALL-E 3画像生成]
        1. OpenAIDalleUseCase を実行して画像を生成
        2. 期待値:
           - 返された MessageDTO に file_path が含まれていること
           - DB (ChatLogs) にファイルパスとモデル名が正しく保存されていること
        """
        # DALL-E サービスと画像処理をモック化
        mock_response = MagicMock()
        mock_response.data = [MagicMock(url="http://example.com/image.jpg")]
        mock_dalle_service.return_value.retrieve_answer.return_value = mock_response

        mock_get_response = MagicMock()
        mock_get_response.content = b"fake_image_content"
        mock_get.return_value = mock_get_response

        mock_img = MagicMock()
        mock_image_open.return_value.resize.return_value = mock_img

        # UseCase 実行
        use_case = OpenAIDalleUseCase()
        result = use_case.execute(self.user, "ねこの画像を生成して")

        # 結果の MessageDTO を検証
        self.assertIsNotNone(result.file_path)
        self.assertEqual(result.model_name, ModelName.DALLE_3)

        # DB への保存を検証
        self._assert_chat_log_saved(ModelName.DALLE_3, UseCaseType.OPENAI_DALLE)

    @patch("llm_chat.domain.service.completion.multimedia.OpenAILlmTextToSpeech")
    def test_tts_usecase_saves_file_path(self, mock_tts_service):
        """
        [シナリオ: TTS音声生成]
        1. OpenAITextToSpeechUseCase を実行して音声を生成
        2. 期待値:
           - 返された MessageDTO に file_path が含まれていること
           - DB (ChatLogs) にファイルパスとモデル名が正しく保存されていること
        """
        # TTS サービスをモック化
        mock_response = MagicMock()
        mock_tts_service.return_value.retrieve_answer.return_value = mock_response

        # UseCase 実行
        use_case = OpenAITextToSpeechUseCase()
        result = use_case.execute(self.user, "こんにちは")

        # 結果の MessageDTO を検証
        self.assertIsNotNone(result.file_path)
        self.assertEqual(result.model_name, ModelName.TTS_1)

        # DB への保存を検証
        self._assert_chat_log_saved(ModelName.TTS_1, UseCaseType.OPENAI_TEXT_TO_SPEECH)

    @patch("llm_chat.domain.service.completion.multimedia.OpenAILlmSpeechToText")
    @patch("llm_chat.domain.service.completion.multimedia.Path.exists")
    def test_stt_usecase_saves_file_path(self, mock_exists, mock_stt_service):
        """
        [シナリオ: STT音声認識]
        1. OpenAISpeechToTextUseCase を実行して音声をテキスト化
        2. 期待値:
           - DB (ChatLogs) にファイルパスとモデル名が正しく保存されていること
        """
        # 前準備
        mock_exists.return_value = True
        mock_stt_service.return_value.retrieve_answer.return_value = MagicMock(
            text="テスト音声です"
        )

        # ダミーのアップロードファイルを作成

        audio_file = SimpleUploadedFile(
            "test.mp3", b"dummy content", content_type="audio/mpeg"
        )

        # UseCase 実行
        with patch("llm_chat.domain.usecase.completion.multimedia.open", create=True):
            use_case = OpenAISpeechToTextUseCase(audio_file)
            result = use_case.execute(self.user, "N/A")

        # 結果の MessageDTO を検証
        self.assertEqual(result.file_path, "llm_chat/audios/test.mp3")
        self.assertEqual(result.model_name, ModelName.WHISPER_1)

        # DB への保存を検証
        last_log = ChatLogs.objects.filter(
            user=self.user, role=RoleType.ASSISTANT.value
        ).last()
        self.assertIsNotNone(last_log)
        self.assertEqual(last_log.file.name, "llm_chat/audios/test.mp3")
        self.assertEqual(last_log.model_name, ModelName.WHISPER_1)
        self.assertEqual(last_log.use_case_type, UseCaseType.OPENAI_SPEECH_TO_TEXT)


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

        factory = RequestFactory()
        request = factory.get("/")
        request.user = self.user
        request.session = SessionStore()

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
            use_case_type=UseCaseType.RIDDLE,
        )
        context = view.get_context_data()
        self.assertTrue(context["is_riddle_active"])

        # 3. なぞなぞ終了メッセージあり -> Riddle 非アクティブ
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.ASSISTANT.value,
            content=f"お疲れ様でした。 {RiddleChatService.RIDDLE_END_MESSAGE}",
            use_case_type=UseCaseType.RIDDLE,
        )
        context = view.get_context_data()
        self.assertFalse(context["is_riddle_active"])

    def test_index_view_initial_use_case_type(self):
        """
        [シナリオ: IndexView の get_initial() による直近ユースケースタイプの取得]
        1. 履歴がない場合: デフォルト値が返ることを確認
        2. 直近の履歴が Gemini の場合: Gemini が返ることを確認
        3. 直近の履歴が Dall-e の場合: OpenAIDalle が返ることを確認
        4. 直近の履歴が なぞなぞ (進行中) の場合: Riddle が返ることを確認
        5. 直近の履歴が なぞなぞ (終了) の場合: 直近の model_name に基づく値が返ることを確認
        """

        factory = RequestFactory()
        request = factory.get("/")
        request.user = self.user
        request.session = SessionStore()

        view = IndexView()
        view.request = request

        # 1. 履歴なし -> デフォルトで UseCaseType.OPENAI_GPT
        initial = view.get_initial()
        self.assertEqual(initial.get("use_case_type"), UseCaseType.OPENAI_GPT)

        # 2. 直近が Gemini
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.USER.value,
            content="Hello",
            model_name=ModelName.GEMINI_2_0_FLASH,
            use_case_type=UseCaseType.GEMINI,
            created_at=timezone.now(),
        )
        time.sleep(0.01)
        initial = view.get_initial()
        self.assertEqual(initial.get("use_case_type"), UseCaseType.GEMINI)

        # 3. 直近が Dall-e
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.ASSISTANT.value,
            content="Image URL",
            model_name=ModelName.DALLE_3,
            use_case_type=UseCaseType.OPENAI_DALLE,
            created_at=timezone.now(),
        )
        time.sleep(0.01)
        initial = view.get_initial()
        self.assertEqual(initial.get("use_case_type"), UseCaseType.OPENAI_DALLE)

        # 4. なぞなぞ (進行中)
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.ASSISTANT.value,
            content="なぞなぞです",
            model_name=ModelName.GPT_5_MINI,
            use_case_type=UseCaseType.RIDDLE,
            created_at=timezone.now(),
        )
        time.sleep(0.01)
        initial = view.get_initial()
        self.assertEqual(initial.get("use_case_type"), UseCaseType.RIDDLE)

        # 5. なぞなぞ (終了) -> 最新ログが Riddle 終了であれば、Riddle 活性は False となり、
        # 最新ログ (Riddle 終了メッセージ) の use_case_type は UseCaseType.RIDDLE だが、
        # 以前の仕様では model_name に基づき OpenAIGpt が選択されていたが、
        # 新しい仕様では終了後も最後の use_case_type である Riddle が選択される
        # （なぞなぞが終了していても、最後になぞなぞをしていたなら次もなぞなぞモードで開始するのが自然なため）
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.ASSISTANT.value,
            content=f"正解です！ {RiddleChatService.RIDDLE_END_MESSAGE}",
            model_name=ModelName.GPT_5_MINI,
            use_case_type=UseCaseType.RIDDLE,
            created_at=timezone.now(),
        )
        initial = view.get_initial()
        self.assertEqual(initial.get("use_case_type"), UseCaseType.RIDDLE)

        # 6. なぞなぞ進行中に別のチャットを挟む -> 最新のログがなぞなぞ以外であれば、その時点でなぞなぞは中断されているとみなす
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.ASSISTANT.value,
            content="なぞなぞ再開",
            model_name=ModelName.GPT_5_MINI,
            use_case_type=UseCaseType.RIDDLE,
            created_at=timezone.now(),
        )
        time.sleep(0.01)
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.USER.value,
            content="横槍チャット",
            model_name=ModelName.GEMINI_2_0_FLASH,
            use_case_type=UseCaseType.GEMINI,
            created_at=timezone.now(),
        )
        initial = view.get_initial()
        # 最新が Gemini なので、Gemini が選択される
        self.assertEqual(initial.get("use_case_type"), UseCaseType.GEMINI)

        # 明示的に、なぞなぞを終了させる
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.ASSISTANT.value,
            content=f"お疲れ様でした。 {RiddleChatService.RIDDLE_END_MESSAGE}",
            model_name=ModelName.GPT_5_MINI,
            use_case_type=UseCaseType.RIDDLE,
            created_at=timezone.now(),
        )

        # 7. ストリーミングモードの復元
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.USER.value,
            content="Streaming request",
            model_name=ModelName.GPT_5_MINI,
            use_case_type=UseCaseType.OPENAI_GPT_STREAMING,
            created_at=timezone.now(),
        )
        initial = view.get_initial()
        self.assertEqual(initial.get("use_case_type"), UseCaseType.OPENAI_GPT_STREAMING)

        # 8. RAGモードの復元
        ChatLogs.objects.create(
            user=self.user,
            role=RoleType.USER.value,
            content="RAG query",
            model_name=ModelName.GPT_5_MINI,
            use_case_type=UseCaseType.OPENAI_RAG,
            created_at=timezone.now(),
        )
        initial = view.get_initial()
        self.assertEqual(initial.get("use_case_type"), UseCaseType.OPENAI_RAG)
