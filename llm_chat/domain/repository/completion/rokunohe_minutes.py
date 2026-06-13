from lib.llm.service.completion import OpenAILlmRagService
from lib.llm.valueobject.completion import Message, RagResponse
from lib.llm.valueobject.config import ModelName
from llm_chat.domain.valueobject.completion.rokunohe_minutes import (
    ROKUNOHE_MINUTES_COLLECTION_NAME,
    RokunoheMinutesCollectionItem,
    RokunoheMinutesDocument,
    RokunoheMinutesPdf,
    RokunoheMinutesThemeSourceChunk,
)

CollectionGetResult = dict[str, list]


class RokunoheMinutesRagRepository:
    """
    六戸町会議録RAGのChroma DB永続化、閲覧用取得、RAG検索を担当するRepository。

    このRepositoryは、PDF取り込みService、コレクションビューア、テーマ分析Serviceの
    3つの入口から使われます。Chroma DBの低レベルAPIを呼び出す責務をここに閉じ込め、
    呼び出し側には用途別のValue Objectを返します。

    1. PDF取り込みでは、source単位の重複確認、既存PDFチャンク削除、upsertを行う。
    2. コレクションビューアでは、本文、メタデータ、日付フィルタを表示用VOへ変換する。
    3. テーマ分析では、本文、メタデータ、embeddingをクラスタリング用VOへ変換する。

    Chromaの集計やソート機能には依存せず、日付絞り込みや表示用整形は
    Python側で行います。分析結果そのものはDjango DB側のRepositoryが扱います。
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
        """
        コレクションビューアで使う表示対象チャンク数を返します。

        source_date_from未指定時はChroma DBのcountをそのまま使います。日付下限が
        指定された場合は、Chromaから本文とメタデータを取得してPython側で絞り込みます。
        これはビューアの「直近1年」表示と、テーマ分析対象の前提を揃えるためです。
        """
        if source_date_from is not None:
            existing = self._rag_service._collection.get(
                include=["documents", "metadatas"],
            )
            return len(self._build_collection_items(existing, source_date_from))

        return self._rag_service._collection.count()

    def list_collection_items(
        self, *, limit: int, offset: int = 0, source_date_from: int | None = None
    ) -> list[RokunoheMinutesCollectionItem]:
        """
        コレクションビューアに表示するChromaチャンク一覧を取得します。

        通常表示ではChroma DBのlimit/offsetを使ってページングします。日付下限指定時は
        Chroma側で十分なフィルタ・ソートを期待せず、全件取得後にPython側で
        source_dateを絞り込み、日付降順に並べてからページングします。
        """
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

    def list_theme_source_chunks(
        self, *, source_date_from: int | None = None
    ) -> list[RokunoheMinutesThemeSourceChunk]:
        """
        テーマ分析Serviceへ渡す本文、メタデータ、embedding付きチャンクを取得します。

        テーマ分析はK-meansでembeddingを必須にするため、本文またはembeddingが欠けた
        Chromaレコードは分析対象から除外します。source_date_fromが指定された場合は
        直近1年などの分析対象期間に入るチャンクだけを返します。
        """
        existing = self._rag_service._collection.get(
            include=["documents", "metadatas", "embeddings"],
        )
        if not existing or not existing["ids"]:
            return []

        ids = existing["ids"]
        documents = existing.get("documents")
        metadatas = existing.get("metadatas")
        embeddings = existing.get("embeddings")
        documents = documents if documents is not None else []
        metadatas = metadatas if metadatas is not None else []
        embeddings = embeddings if embeddings is not None else []
        chunks: list[RokunoheMinutesThemeSourceChunk] = []

        for index, chroma_id in enumerate(ids):
            document = documents[index] if index < len(documents) else ""
            metadata = metadatas[index] if index < len(metadatas) else {}
            embedding = embeddings[index] if index < len(embeddings) else []
            embedding_list = list(embedding) if embedding is not None else []
            source_date_int = self._get_source_date_int(metadata)
            if source_date_from is not None and source_date_int < source_date_from:
                continue
            if not document or not embedding_list:
                continue
            chunks.append(
                RokunoheMinutesThemeSourceChunk(
                    chroma_id=chroma_id,
                    document=document,
                    source=str(metadata.get("source", "")),
                    source_date=str(metadata.get("source_date") or ""),
                    page=metadata.get("page"),
                    chunk_index=metadata.get("chunk_index"),
                    embedding=embedding_list,
                )
            )

        return chunks

    def _build_collection_items(
        self,
        existing: CollectionGetResult,
        source_date_from: int | None = None,
    ) -> list[RokunoheMinutesCollectionItem]:
        """
        Chromaのget結果をビューア表示用VOへ変換します。

        Chromaの戻り値はids/documents/metadatasが別配列になっているため、同じindexを
        1件の表示用データとして組み立てます。本文は一覧表示用に改行を空白へ変換し、
        先頭200文字だけpreviewとして保持します。
        """
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
