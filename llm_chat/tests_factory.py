from unittest.mock import patch
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from llm_chat.domain.valueobject.completion.use_case import UseCaseType
from llm_chat.domain.factory.completion.use_case import UseCaseFactory
from llm_chat.domain.use_case.completion.chat import (
    LlmChatUseCase,
    OpenAIGptStreamingUseCase,
)
from llm_chat.domain.use_case.completion.multimedia import (
    OpenAIDalleUseCase,
    OpenAITextToSpeechUseCase,
    OpenAISpeechToTextUseCase,
)
from llm_chat.domain.use_case.completion.rag import OpenAIRagUseCase
from llm_chat.domain.use_case.completion.riddle import RiddleUseCase
from lib.llm.valueobject.config import GeminiConfig, OpenAIGptConfig


class UseCaseFactoryTest(TestCase):
    def test_create_gemini(self):
        use_case = UseCaseFactory.create(UseCaseType.GEMINI)
        self.assertIsInstance(use_case, LlmChatUseCase)
        self.assertIsInstance(use_case.config, GeminiConfig)

    def test_create_openai_gpt(self):
        use_case = UseCaseFactory.create(UseCaseType.OPENAI_GPT)
        self.assertIsInstance(use_case, LlmChatUseCase)
        self.assertIsInstance(use_case.config, OpenAIGptConfig)

    def test_create_openai_gpt_streaming(self):
        use_case = UseCaseFactory.create(UseCaseType.OPENAI_GPT_STREAMING)
        self.assertIsInstance(use_case, OpenAIGptStreamingUseCase)

    def test_create_openai_dalle(self):
        use_case = UseCaseFactory.create(UseCaseType.OPENAI_DALLE)
        self.assertIsInstance(use_case, OpenAIDalleUseCase)

    def test_create_openai_text_to_speech(self):
        use_case = UseCaseFactory.create(UseCaseType.OPENAI_TEXT_TO_SPEECH)
        self.assertIsInstance(use_case, OpenAITextToSpeechUseCase)

    def test_create_openai_speech_to_text(self):
        audio_file = SimpleUploadedFile(
            "test.mp3", b"dummy content", content_type="audio/mpeg"
        )
        # SpeechToTextUseCaseは初期化時に実際にファイルを保存しようとするため、
        # 保存パスをモック化するか、単に例外が発生しないことを確認。
        # multimedia.py L105付近で MEDIA_ROOT を使用している。
        with patch("llm_chat.domain.use_case.completion.multimedia.open", create=True):
            with patch("llm_chat.domain.use_case.completion.multimedia.Path.mkdir"):
                use_case = UseCaseFactory.create(
                    UseCaseType.OPENAI_SPEECH_TO_TEXT, audio_file=audio_file
                )
                self.assertIsInstance(use_case, OpenAISpeechToTextUseCase)

    def test_create_openai_speech_to_text_no_file(self):
        with self.assertRaisesRegex(
            ValueError, "Audio file is required for SpeechToText"
        ):
            UseCaseFactory.create(UseCaseType.OPENAI_SPEECH_TO_TEXT)

    def test_create_openai_rag(self):
        use_case = UseCaseFactory.create(UseCaseType.OPENAI_RAG)
        self.assertIsInstance(use_case, OpenAIRagUseCase)

    def test_create_riddle(self):
        use_case = UseCaseFactory.create(UseCaseType.RIDDLE)
        self.assertIsInstance(use_case, RiddleUseCase)
        self.assertIsInstance(use_case.config, OpenAIGptConfig)

    def test_create_invalid_type(self):
        with self.assertRaisesRegex(ValueError, "Invalid use case type: InvalidType"):
            UseCaseFactory.create("InvalidType")
