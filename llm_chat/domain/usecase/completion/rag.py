from django.contrib.auth.models import User

from lib.llm.valueobject.completion import RoleType
from llm_chat.domain.service.completion.rag import OpenAIRagChatService
from llm_chat.domain.usecase.completion.base import UseCase
from llm_chat.domain.valueobject.completion.chat import MessageDTO


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
            model_name=chat_service.model_name,
            use_case_type="OpenAIRag",
        )
        assistant_message = chat_service.generate(user_message)
        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model_name=chat_service.model_name,
            use_case_type="OpenAIRag",
        )
