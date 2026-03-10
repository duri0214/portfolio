from abc import ABC, abstractmethod
from pathlib import Path
from typing import Generator

from django.contrib.auth.models import User
from django.core.files.uploadedfile import UploadedFile

from config.settings import MEDIA_ROOT
from lib.llm.service.completion import LlmCompletionStreamingService
from lib.llm.valueobject.completion import RoleType, StreamResponse
from llm_chat.domain.repository.chat import ChatLogRepository
from llm_chat.domain.service.chat import (
    OpenAIChatStreamingService,
    OpenAIDalleChatService,
    OpenAITextToSpeechChatService,
    OpenAISpeechToTextChatService,
    OpenAIRagChatService,
    ChatService,
    RIDDLE_END_MESSAGE,
)
from llm_chat.domain.valueobject.chat import MessageDTO, GenderType, Gender
from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig, ModelName


class UseCase(ABC):
    def __init__(self):
        self.repository = ChatLogRepository()

    @abstractmethod
    def execute(
        self, user: User, content: str | None
    ) -> MessageDTO | Generator[StreamResponse, None, None]:
        pass

    def _insert_assistant_message(
        self,
        user: User,
        content: str,
        model: str,
        is_riddle: bool = False,
        file_path: str | None = None,
    ) -> MessageDTO:
        assistant_message = MessageDTO(
            user=user,
            role=RoleType.ASSISTANT,
            content=content,
            model_name=model,
            is_riddle=is_riddle,
            file_path=file_path,
        )
        self.repository.insert(assistant_message)
        return assistant_message


class LlmChatUseCase(UseCase):
    """統合されたLLMチャットユースケース（GeminiとOpenAI両対応）"""

    def __init__(self, config: OpenAIGptConfig | GeminiConfig):
        super().__init__()
        self.config = config

    def execute(self, user: User, content: str | None) -> MessageDTO:
        if content is None:
            raise ValueError("content cannot be None for LlmChatUseCase")

        chat_service = ChatService(self.config)

        user_message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=content,
            model_name=self.config.model,
            is_riddle=False,
        )

        assistant_message = chat_service.generate(user_message)
        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model=self.config.model,
            is_riddle=False,
        )


class RiddleUseCase(UseCase):
    """なぞなぞユースケース"""

    def __init__(self, config: OpenAIGptConfig | GeminiConfig):
        super().__init__()
        self.config = config

    def execute(self, user: User, content: str | None) -> MessageDTO:
        if content is None:
            raise ValueError("content cannot be None for RiddleUseCase")

        chat_service = ChatService(self.config)

        user_message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=content,
            model_name=self.config.model,
            is_riddle=True,
        )

        # なぞなぞは明示的に is_riddle=True を指定
        assistant_message = chat_service.generate(
            user_message, is_riddle=True, gender=Gender(GenderType.MAN)
        )

        # なぞなぞの終端処理
        if RIDDLE_END_MESSAGE in assistant_message.content:
            evaluation_text = chat_service.evaluate(login_user=user_message.user)
            assistant_message.content += evaluation_text

        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model=self.config.model,
            is_riddle=True,
        )


class OpenAIGptStreamingUseCase(UseCase):
    def execute(
        self, user: User, content: str | None
    ) -> Generator[StreamResponse, None, None]:
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
        user_message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=content,
            model_name=chat_service.config.model,
            is_riddle=False,
        )
        return chat_service.generate(user_message)

    def save(self, user: User, content: str) -> None:
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
        chat_service = OpenAIChatStreamingService()
        self.repository.insert(
            MessageDTO(
                user=user,
                role=RoleType.ASSISTANT,
                content=content,
                model_name=chat_service.config.model,
                is_riddle=False,
            )
        )

    @staticmethod
    def convert_to_sse(stored_stream: Generator[StreamResponse, None, None]):
        return LlmCompletionStreamingService.streaming_from_generator(
            generator=stored_stream
        )


class OpenAIDalleUseCase(UseCase):
    def execute(self, user: User, content: str | None) -> MessageDTO:
        """
        OpenAIDalleServiceを利用し、ユーザーからの入力テキスト（content）を基に画像を生成します。
        contentパラメータはNoneではないこと。

        Args:
            user (User): DjangoのUserモデル of instance
            content (str | None): ユーザーからの入力テキスト

        Raises:
            ValueError: contentがNoneの場合

        Returns:
            画像生成の結果
        """
        if content is None:
            raise ValueError("content cannot be None for OpenAIDalleUseCase")
        chat_service = OpenAIDalleChatService()
        user_message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=content,
            model_name=ModelName.DALLE_3,
            is_riddle=False,
        )
        assistant_message = chat_service.generate(user_message)
        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model=ModelName.DALLE_3,
            is_riddle=False,
            file_path=assistant_message.file_path,
        )


class OpenAITextToSpeechUseCase(UseCase):
    def execute(self, user: User, content: str | None) -> MessageDTO:
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
        user_input_message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=content,
            model_name=ModelName.TTS_1,
            is_riddle=False,
        )
        assistant_message = chat_service.generate(user_input_message)
        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model=ModelName.TTS_1,
            is_riddle=False,
            file_path=assistant_message.file_path,
        )


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
        super().__init__()

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

    def execute(self, user: User, content: str) -> MessageDTO:
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
        init_assistant_message = MessageDTO(
            user=user,
            role=RoleType.ASSISTANT,
            content=content,
            file_path=self.file_path,
            model_name=ModelName.WHISPER_1,
            is_riddle=False,
        )

        assistant_message = chat_service.generate(init_assistant_message)
        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model=ModelName.WHISPER_1,
            is_riddle=False,
            file_path=assistant_message.file_path,
        )


class OpenAIRagUseCase(UseCase):
    def execute(self, user: User, content: str | None) -> MessageDTO:
        """
        RagServiceを利用し、Pdfをソースに。
        contentパラメータは必ずNoneであること。

        Args:
            user (User): DjangoのUserモデルのインスタンス
            content (str | None): この引数は現在利用されていません。

        Raises:
            ValueError: contentがNoneでない場合

        Returns:
            RAG処理の結果
        """
        if content is None:
            raise ValueError("content cannot be None for OpenAIRagUseCase")

        chat_service = OpenAIRagChatService()
        user_message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=content,
            model_name=ModelName.GPT_5_MINI,
            is_riddle=False,
        )
        assistant_message = chat_service.generate(user_message)
        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model=ModelName.GPT_5_MINI,
            is_riddle=False,
        )
