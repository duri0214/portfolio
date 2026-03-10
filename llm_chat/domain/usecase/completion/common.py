from typing import Generator

from django.contrib.auth.models import User

from lib.llm.service.completion import LlmCompletionStreamingService
from lib.llm.valueobject.completion import RoleType, StreamResponse
from lib.llm.valueobject.config import OpenAIGptConfig, GeminiConfig
from llm_chat.domain.service.completion.common import ChatService, OpenAIChatStreamingService
from llm_chat.domain.usecase.completion.base import UseCase
from llm_chat.domain.valueobject.chat import MessageDTO


class LlmChatUseCase(UseCase):
    """統合されたLLMチャットユースケース（GeminiとOpenAI両対応）"""

    def __init__(self, config: OpenAIGptConfig | GeminiConfig):
        super().__init__()
        self.config = config

    def execute(self, user: User, content: str | None) -> MessageDTO:
        if content is None:
            raise ValueError("content cannot be None for LlmChatUseCase")

        chat_service = ChatService(self.config)

        model_name = "Gemini" if isinstance(self.config, GeminiConfig) else "OpenAIGpt"
        user_message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=content,
            model_name=model_name,
            is_riddle=False,
        )

        assistant_message = chat_service.generate(user_message)
        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model_name=model_name,
            is_riddle=False,
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
            model_name="OpenAIGptStreaming",
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
                model_name="OpenAIGptStreaming",
                is_riddle=False,
            )
        )

    @staticmethod
    def convert_to_sse(stored_stream: Generator[StreamResponse, None, None]):
        return LlmCompletionStreamingService.streaming_from_generator(
            generator=stored_stream
        )
