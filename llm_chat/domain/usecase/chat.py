from abc import ABC, abstractmethod
from pathlib import Path

from django.contrib.auth.models import User
from django.core.files.uploadedfile import UploadedFile

from config.settings import MEDIA_ROOT
from lib.llm.valueobject.chat import RoleType
from llm_chat.domain.service.chat import (
    GeminiChatService,
    OpenAIChatService,
    OpenAIChatStreamingService,
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
        return chat_service.generate(message)


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


class OpenAIGptStreamingUseCase(UseCase):
    def execute(self, user: User, content: str | None):
        """
        OpenAIChatStreamingServiceを利用し、ユーザーからの入力（content）を基にテキストを生成します。
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
            raise ValueError("content cannot be None for OpenAIGptStreamingUseCase")
        chat_service = OpenAIChatStreamingService()
        message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=content,
            invisible=False,
        )
        return chat_service.generate(message)

    @staticmethod
    def save(user: User, content: str) -> None:
        """
        ストリーミングの完了後にアシスタントメッセージとしてデータベースに保存するメソッド。

        このメソッドはストリーミング処理終了後に呼び出され、生成されたコンテンツを
        アシスタント役のメッセージとして加工した上でデータベースに保存します。
        メッセージにはユーザー情報と生成コンテンツを付加し、
        OpenAIChatStreamingService の `save` メソッドを使用します。

        Args:
            user (User): Django の User モデルのインスタンス
            content (str): ストリーミングで生成されたアシスタントのメッセージコンテンツ

        Returns:
            None
        """
        messages = [
            MessageDTO(
                user=user,
                role=RoleType.ASSISTANT,
                content=content,
                invisible=False,
            )
        ]
        service = OpenAIChatStreamingService()
        service.save(messages)


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
    def __init__(self, audio_file: UploadedFile):
        """
        初期化で音声ファイルを受け取り、保存処理を行い、後続処理で利用できるようにします。

        Args:
            audio_file (UploadedFile): Django のアップロードファイルオブジェクト

        Raises:
            ValueError: ファイルが指定されていない、または型が正しくない場合
            FileNotFoundError: 保存したファイルが確認できない場合
        """
        # ファイルを保存する（前準備）
        relative_path = f"llm_chat/audios/{audio_file.name}"
        save_path = Path(MEDIA_ROOT) / relative_path
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # ファイルの保存処理
        with open(save_path, "wb") as f:
            for chunk in audio_file.chunks():
                f.write(chunk)

        # 保存後にフルパスと相対パスを設定
        self.full_path = save_path
        if not self.full_path.exists():
            raise FileNotFoundError(
                f"指定された音声ファイル {self.full_path} は存在しません"
            )

        self.file_path = relative_path

    def execute(self, user: User, content: str):
        """
        OpenAISpeechToTextServiceを利用し、ユーザーの最新の音声ファイルをテキストに変換します。
        contentパラメータは必ず 'N/A' であること。

        Args:
            user (User): DjangoのUserモデルのインスタンス
            content (str): この引数は必ず 'N/A' に固定

        Raises:
            ValueError: contentが 'N/A' でない場合

        Returns:
            音声をテキストに変換した結果
        """
        if content != "N/A":
            raise ValueError("content must be 'N/A' for OpenAISpeechToTextUseCase")

        chat_service = OpenAISpeechToTextChatService()
        message = MessageDTO(
            user=user,
            role=RoleType.ASSISTANT,
            content=content,
            file_path=self.file_path,
            invisible=False,
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
