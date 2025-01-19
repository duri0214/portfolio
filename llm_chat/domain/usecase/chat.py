from abc import ABC, abstractmethod
from pathlib import Path

from django.contrib.auth.models import User

from config.settings import MEDIA_ROOT
from lib.llm.valueobject.chat import RoleType
from llm_chat.domain.service.chat import (
    GeminiChatService,
    OpenAIChatService,
    OpenAIDalleChatService,
    OpenAITextToSpeechChatService,
    OpenAISpeechToTextChatService,
    OpenAIRagChatService,
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
        chat_service = GeminiChatService()
        message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=content,
            invisible=False,
        )
        return chat_service.generate(message, gender=Gender(GenderType.MAN))


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
        chat_service = OpenAIChatService()
        message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=content,
            invisible=False,
        )
        return chat_service.generate(message, gender=Gender(GenderType.MAN))


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
        chat_service = OpenAIDalleChatService()
        message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=content,
            invisible=False,
        )
        return chat_service.generate(message)


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
        chat_service = OpenAITextToSpeechChatService()
        message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=content,
            invisible=False,
        )
        return chat_service.generate(message)


class OpenAISpeechToTextUseCase(UseCase):
    def execute(self, user: User, content: str | None):
        """
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

        chat_service = OpenAISpeechToTextChatService()
        message = MessageDTO(
            user=record.user,
            role=RoleType(record.role),
            content=record.content,
            file_path=record.file.name,
            invisible=record.invisible,
        )

        return chat_service.generate(message)


class OpenAIRagUseCase(UseCase):
    def execute(self, user: User, content: str | None):
        """
        RagServiceを利用し、Pdfをソースに。
        contentパラメータは必ずNoneであること。

        Args:
            user (User): DjangoのUserモデルのインスタンス
            content (str | None): この引数は現在利用されていません。

        Raises:
            ValueError: contentがNoneでない場合

        Returns:
            音声をテキストに変換した結果
        """
        if content is None:
            raise ValueError("content cannot be None for OpenAIRagUseCase")
        chat_service = OpenAIRagChatService()
        message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=content,
            invisible=False,
        )
        return chat_service.generate(message)
