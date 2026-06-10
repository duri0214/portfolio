from django.contrib.auth.models import User

from llm_chat.domain.service.completion.rokunohe_minutes import (
    RokunoheMinutesRagService,
)
from llm_chat.domain.use_case.completion.base import UseCase
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class RokunoheMinutesRagUseCase(UseCase):
    def execute(self, user: User, content: str | None) -> MessageDTO:
        """
        RokunoheMinutesRagServiceを利用し、六戸町会議録をソースに質問応答を行う。

        Args:
            user (User): DjangoのUserモデルのインスタンス
            content (str | None): ユーザーの質問内容

        Returns:
            RAG処理の結果
        """
        if content is None:
            raise ValueError("content cannot be None for RokunoheMinutesRagUseCase")

        chat_service = RokunoheMinutesRagService()
        user_message = self._insert_user_message(
            user=user,
            content=content,
            model_name=chat_service.model_name,
            use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
        )
        assistant_message = chat_service.generate(user_message)
        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model_name=chat_service.model_name,
            use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
        )
