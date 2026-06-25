from dataclasses import dataclass
from pathlib import Path


OPENAI_RAG_COLLECTION_NAME = "openai_rag_pdfs"


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

    @property
    def source_name(self) -> str:
        return self.display_name or self.path.name

    @property
    def document_id(self) -> str:
        return f"openai_rag_pdf_{self.pdf_id}"


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

    def to_dict(self) -> dict[str, str | int]:
        return {
            "id": f"{self.pdf.document_id}_page_{self.page}",
            "rag_pdf_id": self.pdf.pdf_id,
            "source": self.pdf.source_name,
            "file_name": self.pdf.path.name,
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
