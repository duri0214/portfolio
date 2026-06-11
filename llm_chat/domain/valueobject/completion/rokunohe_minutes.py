from dataclasses import dataclass
from enum import Enum
from pathlib import Path
import re


ROKUNOHE_MINUTES_COLLECTION_NAME = "rokunohe_minutes"
ROKUNOHE_MINUTES_MEDIA_DIR = Path("llm_chat") / "rokunohe_pdf_back_numbers"


class RokunoheMinutesImportStatus(Enum):
    """
    六戸町会議録PDFのRAG登録結果。

    Attributes:
        IMPORTED: Chroma DBへの登録が完了した状態。
        SKIPPED_EXISTING: 同じPDFが登録済みのためスキップした状態。
        SKIPPED_EMPTY_TEXT: PDFから本文を抽出できずスキップした状態。
    """

    IMPORTED = "imported"
    SKIPPED_EXISTING = "skipped_existing"
    SKIPPED_EMPTY_TEXT = "skipped_empty_text"


@dataclass(frozen=True)
class RokunoheMinutesPdf:
    """
    六戸町会議録PDFファイルを表すValue Object。

    Attributes:
        path: ローカルに保存されたPDFファイルのパス。
    """

    path: Path

    @property
    def source_name(self) -> str:
        return self.path.name

    @property
    def document_id(self) -> str:
        return f"rokunohe_{self.path.stem}"

    @property
    def source_date(self) -> str:
        match = re.match(r"^(?P<date>\d{8})_", self.path.name)
        return match.group("date") if match else ""


@dataclass(frozen=True)
class RokunoheMinutesMetadata:
    """
    六戸町会議録をChroma DBへ登録する際のメタデータ。

    Attributes:
        source: 出典として表示・重複判定に使うPDFファイル名。
        document_id: Chroma DBへ登録するドキュメントIDの基礎値。
        source_date: PDFファイル名先頭から取得したYYYYMMDD形式の日付。
        page: PDF内のページ番号。
        chunk_index: RAG登録時のチャンク番号。
    """

    source: str
    document_id: str
    source_date: str = ""
    page: int | None = None
    chunk_index: int | None = None

    @classmethod
    def from_pdf(
        cls,
        pdf: RokunoheMinutesPdf,
        *,
        page: int | None = None,
        chunk_index: int | None = None,
    ) -> "RokunoheMinutesMetadata":
        return cls(
            source=pdf.source_name,
            document_id=pdf.document_id,
            source_date=pdf.source_date,
            page=page,
            chunk_index=chunk_index,
        )

    def to_dict(self) -> dict[str, str | int]:
        document_id = self.document_id
        if self.page is not None:
            document_id = f"{document_id}_page_{self.page}"

        metadata: dict[str, str | int] = {
            "source": self.source,
            "id": document_id,
        }
        if self.source_date:
            metadata["source_date"] = self.source_date
        if self.page is not None:
            metadata["page"] = self.page
        if self.chunk_index is not None:
            metadata["chunk_index"] = self.chunk_index
        return metadata


@dataclass(frozen=True)
class RokunoheMinutesDocument:
    """
    六戸町会議録RAGへ登録する1件分のドキュメント。

    Attributes:
        page_content: PDFから抽出した本文。
        metadata: Chroma DB登録時に付与する出典情報。
    """

    page_content: str
    metadata: dict[str, str | int]
