import os

from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig, ModelName
from llm_chat.domain.use_case.completion.chat import (
    LlmChatUseCase,
    OpenAIGptStreamingUseCase,
)
from llm_chat.domain.use_case.completion.multimedia import (
    OpenAIImageUseCase,
    OpenAITextToSpeechUseCase,
    OpenAISpeechToTextUseCase,
)
from llm_chat.domain.use_case.completion.rag import OpenAIRagUseCase
from llm_chat.domain.use_case.completion.riddle import RiddleUseCase
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class UseCaseFactory:
    """UseCaseのインスタンスを生成するファクトリクラス"""

    @staticmethod
    def create(use_case_type, **kwargs):
        """
        指定されたUseCaseTypeに応じたUseCaseインスタンスを生成します。

        Args:
            use_case_type (str): ユースケースのタイプ
            **kwargs: 各UseCaseの初期化に必要なパラメータ
                - audio_file (UploadedFile): SpeechToTextで必須

        Returns:
            UseCase: 生成されたUseCaseインスタンス

        Raises:
            ValueError: 不正なUseCaseTypeまたは必須パラメータが不足している場合
        """
        if use_case_type in (UseCaseType.GEMINI, UseCaseType.OPENAI_GPT):
            if use_case_type == UseCaseType.GEMINI:
                config = GeminiConfig(
                    api_key=os.getenv("GEMINI_API_KEY"),
                    max_tokens=4000,
                    model=ModelName.GEMINI_2_0_FLASH,
                )
            else:
                config = OpenAIGptConfig(
                    api_key=os.getenv("OPENAI_API_KEY"),
                    max_tokens=4000,
                    model=ModelName.GPT_5_MINI,
                )
            return LlmChatUseCase(config)

        if use_case_type == UseCaseType.OPENAI_GPT_STREAMING:
            return OpenAIGptStreamingUseCase()

        if use_case_type == UseCaseType.OPENAI_IMAGE:
            return OpenAIImageUseCase()

        if use_case_type == UseCaseType.OPENAI_TEXT_TO_SPEECH:
            return OpenAITextToSpeechUseCase()

        if use_case_type == UseCaseType.OPENAI_SPEECH_TO_TEXT:
            audio_file = kwargs.get("audio_file")
            if not audio_file:
                raise ValueError("Audio file is required for SpeechToText")
            return OpenAISpeechToTextUseCase(audio_file=audio_file)

        if use_case_type == UseCaseType.OPENAI_RAG:
            return OpenAIRagUseCase()

        if use_case_type == UseCaseType.RIDDLE:
            config = OpenAIGptConfig(
                api_key=os.getenv("OPENAI_API_KEY"),
                max_tokens=4000,
                model=ModelName.GPT_5_MINI,
            )
            return RiddleUseCase(config)

        raise ValueError(f"Invalid use case type: {use_case_type}")
