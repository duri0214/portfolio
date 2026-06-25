from django.utils import timezone

from lib.llm.service.completion import OpenAILlmRagService
from lib.llm.valueobject.completion import Message, RagResponse
from lib.llm.valueobject.config import ModelName
from llm_chat.domain.valueobject.completion.rag import (
    OPENAI_RAG_COLLECTION_NAME,
    OpenAIRagDocument,
    OpenAIRagPdfSource,
)
from llm_chat.models import OpenAIRagPdf


class OpenAIRagPdfRepository:
    """
    OpenAI RAG PDFのDjango DB永続化を担当するRepository。

    Service層がDjangoモデルのクエリ操作に直接依存しないよう、PDF選択肢の取得、
    登録対象PDFの取得、Vector DB登録日時の更新をここに閉じ込めます。
    """

    @staticmethod
    def list_active_choices() -> list[tuple[str, str]]:
        return [
            (str(pdf.id), pdf.display_name)
            for pdf in OpenAIRagPdf.objects.filter(is_active=True)
        ]

    @staticmethod
    def list_active() -> list[OpenAIRagPdf]:
        return list(OpenAIRagPdf.objects.filter(is_active=True))

    @staticmethod
    def find_active(pdf_id: int) -> OpenAIRagPdfSource:
        pdf = OpenAIRagPdf.objects.get(id=pdf_id, is_active=True)
        return OpenAIRagPdfSource(
            pdf_id=pdf.id,
            display_name=pdf.display_name,
            path=pdf.file.path,
        )

    @staticmethod
    def exists_active(pdf_id: int) -> bool:
        return OpenAIRagPdf.objects.filter(id=pdf_id, is_active=True).exists()

    @staticmethod
    def mark_imported(pdf_id: int) -> None:
        pdf = OpenAIRagPdf.objects.get(id=pdf_id)
        pdf.imported_at = timezone.now()
        OpenAIRagPdf.objects.bulk_update([pdf], ["imported_at"])


class OpenAIRagVectorRepository:
    """
    OpenAI RAG PDFのChroma DB永続化と回答生成を担当するRepository。

    PDFごとのmetadataに `rag_pdf_id` を保持し、チャット時は選択されたPDFだけを
    検索対象にします。
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = ModelName.GPT_5_MINI,
        collection_name: str = OPENAI_RAG_COLLECTION_NAME,
    ) -> None:
        self._rag_service = OpenAILlmRagService(
            model=model,
            api_key=api_key,
            collection_name=collection_name,
        )

    def upsert_documents(self, documents: list[OpenAIRagDocument]) -> None:
        self._rag_service.upsert_documents(documents)

    def delete_pdf_documents(self, pdf: OpenAIRagPdfSource) -> int:
        existing = self._rag_service._collection.get(where={"rag_pdf_id": pdf.pdf_id})
        if not existing or not existing["ids"]:
            return 0

        self._rag_service._collection.delete(ids=existing["ids"])
        return len(existing["ids"])

    def retrieve_answer(self, message: Message, *, pdf_id: int) -> RagResponse:
        return self._rag_service.retrieve_answer(
            message,
            where_filter={"rag_pdf_id": pdf_id},
        )
