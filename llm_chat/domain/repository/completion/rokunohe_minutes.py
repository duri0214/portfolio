from lib.llm.service.completion import OpenAILlmRagService
from lib.llm.valueobject.completion import Message, RagResponse
from lib.llm.valueobject.config import ModelName
from llm_chat.domain.valueobject.completion.rokunohe_minutes import (
    ROKUNOHE_MINUTES_COLLECTION_NAME,
    RokunoheMinutesCollectionItem,
    RokunoheMinutesDocument,
    RokunoheMinutesPdf,
)

CollectionGetResult = dict[str, list]


class RokunoheMinutesRagRepository:
    """
    六戸町会議録RAGのChroma DB永続化と検索を担当するRepository。
    """

    def __init__(
        self,
        *,
        api_key: str,
        model: str = ModelName.GPT_5_MINI,
        collection_name: str = ROKUNOHE_MINUTES_COLLECTION_NAME,
    ) -> None:
        self._rag_service = OpenAILlmRagService(
            model=model,
            api_key=api_key,
            collection_name=collection_name,
        )

    def exists(self, pdf: RokunoheMinutesPdf) -> bool:
        existing = self._rag_service._collection.get(
            where={"source": pdf.source_name}, limit=1
        )
        return bool(existing and existing["ids"])

    def upsert_documents(self, documents: list[RokunoheMinutesDocument]) -> None:
        self._rag_service.upsert_documents(documents)

    def delete_pdf_documents(self, pdf: RokunoheMinutesPdf) -> None:
        existing = self._rag_service._collection.get(where={"source": pdf.source_name})
        if existing and existing["ids"]:
            self._rag_service._collection.delete(ids=existing["ids"])

    def reset_collection(self) -> int:
        existing = self._rag_service._collection.get()
        if not existing or not existing["ids"]:
            return 0

        self._rag_service._collection.delete(ids=existing["ids"])
        return len(existing["ids"])

    def count_collection_items(self, *, source_date_from: int | None = None) -> int:
        if source_date_from is not None:
            existing = self._rag_service._collection.get(
                include=["documents", "metadatas"],
            )
            return len(self._build_collection_items(existing, source_date_from))

        return self._rag_service._collection.count()

    def list_collection_items(
        self, *, limit: int, offset: int = 0, source_date_from: int | None = None
    ) -> list[RokunoheMinutesCollectionItem]:
        if source_date_from is not None:
            existing = self._rag_service._collection.get(
                include=["documents", "metadatas"],
            )
            items = self._build_collection_items(existing, source_date_from)
            items.sort(
                key=lambda item: self._get_item_source_date_int(item), reverse=True
            )
            return items[offset : offset + limit]

        existing = self._rag_service._collection.get(
            limit=limit,
            offset=offset,
            include=["documents", "metadatas"],
        )
        return self._build_collection_items(existing)

    def _build_collection_items(
        self,
        existing: CollectionGetResult,
        source_date_from: int | None = None,
    ) -> list[RokunoheMinutesCollectionItem]:
        if not existing or not existing["ids"]:
            return []

        ids = existing["ids"]
        documents = existing.get("documents") or []
        metadatas = existing.get("metadatas") or []
        items: list[RokunoheMinutesCollectionItem] = []

        for index, chroma_id in enumerate(ids):
            document = documents[index] if index < len(documents) else ""
            metadata = metadatas[index] if index < len(metadatas) else {}
            source_date_int = self._get_source_date_int(metadata)
            if source_date_from is not None and source_date_int < source_date_from:
                continue
            preview = document.replace("\n", " ")[:200]
            items.append(
                RokunoheMinutesCollectionItem(
                    chroma_id=chroma_id,
                    source=str(metadata.get("source", "")),
                    source_date=str(metadata.get("source_date", "")),
                    page=metadata.get("page"),
                    chunk_index=metadata.get("chunk_index"),
                    preview=preview,
                )
            )

        return items

    @staticmethod
    def _get_source_date_int(metadata: dict) -> int:
        source_date = metadata.get("source_date_ymd") or metadata.get("source_date")
        try:
            return int(source_date)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _get_item_source_date_int(item: RokunoheMinutesCollectionItem) -> int:
        try:
            return int(item.source_date)
        except ValueError:
            return 0

    def retrieve_answer(self, message: Message) -> RagResponse:
        return self._rag_service.retrieve_answer(message)
