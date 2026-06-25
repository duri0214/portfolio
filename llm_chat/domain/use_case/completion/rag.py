from django.contrib.auth.models import User

from llm_chat.domain.repository.completion.rag import OpenAIRagPdfRepository
from llm_chat.domain.service.completion.rag import OpenAIRagService
from llm_chat.domain.use_case.completion.base import UseCase
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class OpenAIRagUseCase(UseCase):
    def execute(
        self, user: User, content: str | None, *, rag_pdf_id: str | None = None
    ) -> MessageDTO:
        """
        RagServiceを利用し、選択されたPDFをソースに回答します。

        Args:
            user (User): DjangoのUserモデルのインスタンス
            content (str | None): ユーザーの質問文。
            rag_pdf_id (str | None): チャット画面で選択されたOpenAIRagPdf ID。

        Raises:
            ValueError: contentまたはrag_pdf_idが未指定の場合。

        Returns:
            RAG処理の結果
        """
        if content is None:
            raise ValueError("content cannot be None for OpenAIRagUseCase")
        if not rag_pdf_id:
            raise ValueError("RAGに使用するPDFを選択してください。")

        try:
            pdf_id = int(rag_pdf_id)
        except ValueError as e:
            raise ValueError("RAGに使用するPDFの指定が不正です。") from e
        if not OpenAIRagPdfRepository.exists_active(pdf_id):
            raise ValueError("選択されたPDFが見つかりません。")

        chat_service = OpenAIRagService()
        user_message = self._insert_user_message(
            user=user,
            content=content,
            model_name=chat_service.model_name,
            use_case_type=UseCaseType.OPENAI_RAG,
        )
        assistant_message = chat_service.generate(user_message, pdf_id=pdf_id)
        return self._insert_assistant_message(
            user=user,
            content=assistant_message.content,
            model_name=chat_service.model_name,
            use_case_type=UseCaseType.OPENAI_RAG,
        )
