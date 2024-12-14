from abc import ABC, abstractmethod
from pathlib import Path

from django.contrib.auth.models import User
from django.core.exceptions import ObjectDoesNotExist

from config import settings
from lib.llm.valueobject.chat import RoleType
from llm_chat.domain.repository.chat import ChatLogRepository
from llm_chat.domain.service.llm import (
    GeminiService,
    OpenAIGptService,
    OpenAIDalleService,
    OpenAITextToSpeechService,
    OpenAISpeechToTextService,
)
from llm_chat.domain.valueobject.chat import MessageDTO, GenderType, Gender


class UseCase(ABC):
    @abstractmethod
    def execute(self, user: User, content: str | None):
        pass


class GeminiUseCase(UseCase):
    def execute(self, user: User, content: str | None):
        """
        GeminiServiceを利用し、ユーザーからの入力（content）を基にテキストを生成します。
        contentパラメータはNoneではないこと。

        Args:
            user (User): DjangoのUserモデルのインスタンス
            content (str | None): ユーザーからの入力テキスト

        Raises:
            ValueError: contentがNoneの場合

        Returns:
            テキスト生成の結果
        """
        if content is None:
            raise ValueError("content cannot be None for GeminiUseCase")
        llm_service = GeminiService()
        message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=content,
            invisible=False,
        )
        return llm_service.generate(message, gender=Gender(GenderType.MAN))


class OpenAIGptUseCase(UseCase):
    def execute(self, user: User, content: str | None):
        """
        OpenAIGptServiceを利用し、ユーザーからの入力（content）を基にテキストを生成します。
        contentパラメータはNoneではないこと。

        Args:
            user (User): DjangoのUserモデルのインスタンス
            content (str | None): ユーザーからの入力テキスト

        Raises:
            ValueError: contentがNoneの場合

        Returns:
            テキスト生成の結果
        """
        if content is None:
            raise ValueError("content cannot be None for OpenAIGptUseCase")
        llm_service = OpenAIGptService()
        message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=content,
            invisible=False,
        )
        return llm_service.generate(message, gender=Gender(GenderType.MAN))


class OpenAIDalleUseCase(UseCase):
    def execute(self, user: User, content: str | None):
        """
        OpenAIDalleServiceを利用し、ユーザーからの入力テキスト（content）を基に画像を生成します。
        contentパラメータはNoneではないこと。

        Args:
            user (User): DjangoのUserモデルのインスタンス
            content (str | None): ユーザーからの入力テキスト

        Raises:
            ValueError: contentがNoneの場合

        Returns:
            画像生成の結果
        """
        if content is None:
            raise ValueError("content cannot be None for OpenAIDalleUseCase")
        llm_service = OpenAIDalleService()
        message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=content,
            invisible=False,
        )
        return llm_service.generate(message)


class OpenAITextToSpeechUseCase(UseCase):
    def execute(self, user: User, content: str | None):
        """
        OpenAITextToSpeechServiceを利用し、ユーザーからの入力テキスト（content）を基に音声を生成します。
        contentパラメータはNoneではないこと。

        Args:
            user (User): DjangoのUserモデルのインスタンス
            content (str | None): ユーザーからの入力テキスト

        Raises:
            ValueError: contentがNoneの場合

        Returns:
            音声生成の結果
        """
        if content is None:
            raise ValueError("content cannot be None for OpenAITextToSpeechUseCase")
        llm_service = OpenAITextToSpeechService()
        message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=content,
            invisible=False,
        )
        return llm_service.generate(message)


class OpenAISpeechToTextUseCase(UseCase):
    def execute(self, user: User, content: str | None):
        """
        TODO: ちょっとファイルが見つけられないバグがある issue7
        OpenAISpeechToTextServiceを利用し、ユーザーの最新の音声ファイルをテキストに変換します。
        contentパラメータは必ずNoneであること。

        Args:
            user (User): DjangoのUserモデルのインスタンス
            content (str | None): この引数は現在利用されていません。

        Raises:
            ValueError: contentがNoneでない場合

        Returns:
            音声をテキストに変換した結果
        """
        if content is not None:
            raise ValueError("content must be None for OpenAISpeechToTextUseCase")
        record = ChatLogRepository.find_last_audio_log(user)

        if record is None:
            raise ObjectDoesNotExist("No audio file registered for the user")

        llm_service = OpenAISpeechToTextService()
        message = MessageDTO(
            user=record.user,
            role=record.role,
            content=record.content,
            file_path=str(Path(settings.MEDIA_ROOT) / record.file_path),
            invisible=record.invisible,
        )

        return llm_service.generate(message)
