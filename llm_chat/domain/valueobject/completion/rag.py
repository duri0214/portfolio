from dataclasses import dataclass
from pathlib import Path


OPENAI_RAG_COLLECTION_NAME = "openai_rag_pdfs"
OPENAI_RAG_COLLECTION_PREFIX = "openai_rag_pdf"
OPENAI_RAG_EMBEDDING_MODEL = "text-embedding-3-small"
OPENAI_RAG_CHUNK_BASIS = "page"


def build_openai_rag_collection_name(pdf_id: int) -> str:
    return f"{OPENAI_RAG_COLLECTION_PREFIX}_{pdf_id}"


def build_openai_rag_collection_label(
    *,
    source_extension_label: str,
    source_name: str,
    imported_at: str,
    embedding_model: str = OPENAI_RAG_EMBEDDING_MODEL,
) -> str:
    return (
        f"{source_extension_label}｜{source_name}｜" f"{embedding_model}｜{imported_at}"
    )


@dataclass(frozen=True)
class OpenAIRagPdfSource:
    """
    OpenAI RAGに登録するPDFファイルを表すValue Object。

    Attributes:
        pdf_id: Django DB上のPDF ID。
        display_name: ユーザー向けの表示名。
        path: ローカルに保存されたPDFファイルのパス。
    """

    pdf_id: int
    display_name: str
    path: Path
    collection_name: str

    @property
    def source_name(self) -> str:
        return self.display_name or self.path.name

    @property
    def document_id(self) -> str:
        return f"openai_rag_pdf_{self.pdf_id}"

    @property
    def source_extension_label(self) -> str:
        suffix = self.path.suffix.lstrip(".")
        return suffix.upper() if suffix else "UNKNOWN"


@dataclass(frozen=True)
class OpenAIRagPdfMetadata:
    """
    OpenAI RAG PDFをChroma DBへ登録する際のメタデータ。

    Attributes:
        pdf: 登録対象のPDF。
        page: PDF内のページ番号。
        chunk_index: RAG登録時のチャンク番号。
    """

    pdf: OpenAIRagPdfSource
    page: int
    chunk_index: int
    imported_at: str
    embedding_model: str = OPENAI_RAG_EMBEDDING_MODEL
    chunk_basis: str = OPENAI_RAG_CHUNK_BASIS

    def to_dict(self) -> dict[str, str | int]:
        collection_label = build_openai_rag_collection_label(
            source_extension_label=self.pdf.source_extension_label,
            source_name=self.pdf.source_name,
            embedding_model=self.embedding_model,
            imported_at=self.imported_at,
        )
        return {
            "id": f"{self.pdf.document_id}_page_{self.page}",
            "rag_pdf_id": self.pdf.pdf_id,
            "collection_name": self.pdf.collection_name,
            "collection_label": collection_label,
            "embedding_model": self.embedding_model,
            "chunk_basis": self.chunk_basis,
            "source": self.pdf.source_name,
            "file_name": self.pdf.source_name,
            "stored_file_name": self.pdf.path.name,
            "imported_at": self.imported_at,
            "page": self.page,
            "chunk_index": self.chunk_index,
        }


@dataclass(frozen=True)
class OpenAIRagDocument:
    """
    OpenAI RAGへ登録する1件分のドキュメント。

    Attributes:
        page_content: PDFから抽出した本文。
        metadata: Chroma DB登録時に付与する出典情報。
    """

    page_content: str
    metadata: dict[str, str | int]


@dataclass(frozen=True)
class OpenAIRagCollectionItem:
    """
    Chroma DBに登録済みのOpenAI RAG PDFドキュメント1件分の表示用データ。
    """

    chroma_id: str
    collection_name: str
    collection_label: str
    source: str
    file_name: str
    embedding_model: str
    chunk_basis: str
    imported_at: str
    page: int | None
    chunk_index: int | None
    preview: str
