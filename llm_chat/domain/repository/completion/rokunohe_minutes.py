from lib.llm.service.completion import OpenAILlmRagService
from lib.llm.valueobject.completion import Message, RagResponse
from lib.llm.valueobject.config import ModelName
from llm_chat.domain.valueobject.completion.rokunohe_minutes import (
    ROKUNOHE_MINUTES_COLLECTION_NAME,
    RokunoheMinutesDocument,
    RokunoheMinutesPdf,
)


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

    def retrieve_answer(self, message: Message) -> RagResponse:
        return self._rag_service.retrieve_answer(message)
