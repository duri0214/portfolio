from dataclasses import dataclass
from enum import Enum
from pathlib import Path


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


@dataclass(frozen=True)
class RokunoheMinutesMetadata:
    """
    六戸町会議録をChroma DBへ登録する際のメタデータ。

    Attributes:
        source: 出典として表示・重複判定に使うPDFファイル名。
        document_id: Chroma DBへ登録するドキュメントIDの基礎値。
    """

    source: str
    document_id: str

    @classmethod
    def from_pdf(cls, pdf: RokunoheMinutesPdf) -> "RokunoheMinutesMetadata":
        return cls(source=pdf.source_name, document_id=pdf.document_id)

    def to_dict(self) -> dict[str, str]:
        return {
            "source": self.source,
            "id": self.document_id,
        }


@dataclass(frozen=True)
class RokunoheMinutesDocument:
    """
    六戸町会議録RAGへ登録する1件分のドキュメント。

    Attributes:
        page_content: PDFから抽出した本文。
        metadata: Chroma DB登録時に付与する出典情報。
    """

    page_content: str
    metadata: dict[str, str]
