from datetime import datetime
from pathlib import Path

from lib.llm.service.completion import OpenAILlmRagService
from lib.llm.valueobject.completion import Message, RagResponse
from lib.llm.valueobject.config import ModelName
from llm_chat.domain.valueobject.completion.rag import (
    OPENAI_RAG_EMBEDDING_MODEL,
    OPENAI_RAG_COLLECTION_NAME,
    OpenAIRagCollectionItem,
    OpenAIRagDocument,
    OpenAIRagPdfSource,
    build_openai_rag_collection_name,
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
            (str(pdf.id), pdf.collection_label)
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
            path=Path(pdf.display_name),
            collection_name=pdf.collection_name
            or build_openai_rag_collection_name(pdf.id),
        )

    @staticmethod
    def exists_active(pdf_id: int) -> bool:
        return OpenAIRagPdf.objects.filter(id=pdf_id, is_active=True).exists()

    @staticmethod
    def mark_imported(pdf_id: int, *, imported_at: datetime) -> None:
        pdf = OpenAIRagPdf.objects.get(id=pdf_id)
        pdf.imported_at = imported_at
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
        embedding_model: str = OPENAI_RAG_EMBEDDING_MODEL,
    ) -> None:
        self._rag_service = OpenAILlmRagService(
            model=model,
            api_key=api_key,
            collection_name=collection_name,
            embedding_model=embedding_model,
        )

    def upsert_documents(self, documents: list[OpenAIRagDocument]) -> None:
        self._rag_service.upsert_documents(documents)

    def delete_pdf_documents(self, pdf: OpenAIRagPdfSource) -> int:
        existing = self._rag_service._collection.get(where={"rag_pdf_id": pdf.pdf_id})
        if not existing or not existing["ids"]:
            return 0

        self._rag_service._collection.delete(ids=existing["ids"])
        return len(existing["ids"])

    def delete_all_documents(self) -> int:
        existing = self._rag_service._collection.get()
        if not existing or not existing["ids"]:
            return 0

        self._rag_service._collection.delete(ids=existing["ids"])
        return len(existing["ids"])

    def count_collection_items(self, *, pdf_id: int | None = None) -> int:
        if pdf_id is None:
            return self._rag_service._collection.count()

        existing = self._rag_service._collection.get(
            where={"rag_pdf_id": pdf_id},
        )
        return len(existing["ids"]) if existing and existing["ids"] else 0

    def list_collection_items(
        self, *, limit: int, offset: int = 0, pdf_id: int | None = None
    ) -> list[OpenAIRagCollectionItem]:
        where = {"rag_pdf_id": pdf_id} if pdf_id is not None else None
        existing = self._rag_service._collection.get(
            limit=limit,
            offset=offset,
            where=where,
            include=["documents", "metadatas"],
        )
        return self._build_collection_items(existing)

    @staticmethod
    def _build_collection_items(
        existing: dict[str, list],
    ) -> list[OpenAIRagCollectionItem]:
        if not existing or not existing["ids"]:
            return []

        ids = existing["ids"]
        documents = existing.get("documents") or []
        metadatas = existing.get("metadatas") or []
        items: list[OpenAIRagCollectionItem] = []

        for index, chroma_id in enumerate(ids):
            document = documents[index] if index < len(documents) else ""
            metadata = metadatas[index] if index < len(metadatas) else {}
            preview = document.replace("\n", " ")[:200]
            items.append(
                OpenAIRagCollectionItem(
                    chroma_id=chroma_id,
                    collection_name=str(metadata.get("collection_name", "")),
                    collection_label=str(
                        metadata.get("collection_label")
                        or metadata.get("collection_name", "")
                    ),
                    source=str(metadata.get("source", "")),
                    file_name=str(metadata.get("file_name", "")),
                    embedding_model=str(metadata.get("embedding_model", "")),
                    chunk_basis=str(metadata.get("chunk_basis", "")),
                    imported_at=str(metadata.get("imported_at", "")),
                    page=metadata.get("page"),
                    chunk_index=metadata.get("chunk_index"),
                    preview=preview,
                )
            )

        return items

    def retrieve_answer(self, message: Message, *, pdf_id: int) -> RagResponse:
        return self._rag_service.retrieve_answer(
            message,
            where_filter={"rag_pdf_id": pdf_id},
        )
