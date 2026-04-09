from unittest.mock import patch, MagicMock

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase

from lib.llm.valueobject.completion import RoleType
from lib.llm.valueobject.config import ModelName
from llm_chat.domain.use_case.completion.multimedia import (
    OpenAIImageUseCase,
    OpenAITextToSpeechUseCase,
    OpenAISpeechToTextUseCase,
)
from llm_chat.domain.valueobject.completion.use_case import UseCaseType
from llm_chat.models import ChatLogs


class OpenAiMultimediaUseCaseTest(TestCase):
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

    @patch("llm_chat.domain.service.completion.multimedia.OpenAILlmImageService")
    @patch("llm_chat.domain.service.completion.multimedia.requests.get")
    @patch("llm_chat.domain.service.completion.multimedia.Image.open")
    def test_image_use_case_saves_file_path(
        self, mock_image_open, mock_get, mock_image_service
    ):
        """
        [シナリオ: OpenAI画像生成]
        1. OpenAIImageUseCase を実行して画像を生成
        2. 期待値:
           - 返された MessageDTO に file_path が含まれていること
           - DB (ChatLogs) にファイルパスとモデル名が正しく保存されていること
        """
        # 画像生成サービスと画像処理をモック化
        mock_response = MagicMock()
        mock_response.data = [MagicMock(url="http://example.com/image.jpg")]
        mock_image_service.return_value.retrieve_answer.return_value = mock_response

        mock_get_response = MagicMock()
        mock_get_response.content = b"fake_image_content"
        mock_get.return_value = mock_get_response

        # UseCase 実行
        use_case = OpenAIImageUseCase()
        result = use_case.execute(self.user, "ねこの画像を生成して")

        # 結果の MessageDTO を検証
        self.assertIsNotNone(result.file_path)
        self.assertEqual(result.model_name, ModelName.GPT_IMAGE_1_MINI)

        # DB への保存を検証
        self._assert_chat_log_saved(
            ModelName.GPT_IMAGE_1_MINI, UseCaseType.OPENAI_IMAGE
        )

    @patch("llm_chat.domain.service.completion.multimedia.OpenAILlmTextToSpeech")
    def test_tts_use_case_saves_file_path(self, mock_tts_service):
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
    def test_stt_use_case_saves_user_and_assistant_logs(
        self, mock_exists, mock_stt_service
    ):
        """
        [シナリオ: STT音声認識]
        1. OpenAISpeechToTextUseCase を実行して音声をテキスト化
        2. 期待値:
           - USER メッセージがファイルパス付きで DB に保存されていること
           - ASSISTANT メッセージが文字起こし結果付きで DB に保存されていること
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
        with patch("llm_chat.domain.use_case.completion.multimedia.open", create=True):
            use_case = OpenAISpeechToTextUseCase(audio_file)
            result = use_case.execute(self.user, "N/A")

        # USER メッセージの検証
        user_log = ChatLogs.objects.filter(
            user=self.user, role=RoleType.USER.value
        ).last()
        self.assertIsNotNone(user_log)
        self.assertEqual(user_log.file.name, "llm_chat/audios/test.mp3")
        self.assertEqual(user_log.content, "N/A")
        self.assertEqual(user_log.model_name, ModelName.WHISPER_1)

        # ASSISTANT メッセージの検証
        assistant_log = ChatLogs.objects.filter(
            user=self.user, role=RoleType.ASSISTANT.value
        ).last()
        self.assertIsNotNone(assistant_log)
        # ASSISTANT側には音声ファイルを表示しない仕様に変更
        self.assertEqual(assistant_log.file.name, "")
        self.assertIn("テスト音声です", assistant_log.content)
        self.assertEqual(assistant_log.model_name, ModelName.WHISPER_1)
        self.assertEqual(assistant_log.use_case_type, UseCaseType.OPENAI_SPEECH_TO_TEXT)
