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
        SKIPPED_OUT_OF_SOURCE_DATE_RANGE: PDFの日付が取り込み対象期間外のためスキップした状態。
        SKIPPED_EMPTY_TEXT: PDFから本文を抽出できずスキップした状態。
    """

    IMPORTED = "imported"
    SKIPPED_EXISTING = "skipped_existing"
    SKIPPED_OUT_OF_SOURCE_DATE_RANGE = "skipped_out_of_source_date_range"
    SKIPPED_EMPTY_TEXT = "skipped_empty_text"


@dataclass(frozen=True)
class RokunoheMinutesPdf:
    """
    六戸町会議録PDFファイルを表すValue Object。

    保存ファイル名は、可能な場合 `YYYYMMDD_元のPDF名.pdf` 形式に正規化します。
    この日付は取り込み期間フィルタ、Chroma metadata、テーマ分析の直近1年判定で
    共通して使うため、PDFそのものからsource名、document_id、source_dateを導出します。

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

    ページ単位でChromaへ登録するため、sourceとdocument_idだけでなく、
    page/chunk_index/source_dateも同じmetadataにまとめます。後続のコレクションビューア、
    テーマ分析、出典表示はこのmetadataを前提に同じチャンクを追跡します。

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
        """
        Chroma DBへ渡すmetadata dictを生成します。

        ChromaのIDとして使う `id` はPDF単位のdocument_idにページ番号を加えたものです。
        source_dateは文字列表示用と数値フィルタ用の両方を保存し、Repository側で
        直近1年や明示期間の絞り込みに使えるようにします。
        """
        document_id = self.document_id
        if self.page is not None:
            document_id = f"{document_id}_page_{self.page}"

        metadata: dict[str, str | int] = {
            "source": self.source,
            "id": document_id,
        }
        if self.source_date:
            metadata["source_date"] = self.source_date
            metadata["source_date_ymd"] = int(self.source_date)
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


@dataclass(frozen=True)
class RokunoheMinutesCollectionItem:
    """
    Chroma DBに登録済みの六戸町会議録RAGドキュメント1件分の表示用データ。

    Attributes:
        chroma_id: Chroma DB上のドキュメントID。
        source: 出典PDFファイル名。
        source_date: 出典PDFファイル名から取得したYYYYMMDD形式の日付。
        page: PDF内のページ番号。
        chunk_index: RAG登録時のチャンク番号。
        preview: 管理画面で確認する本文プレビュー。
    """

    chroma_id: str
    source: str
    source_date: str
    page: int | None
    chunk_index: int | None
    preview: str


@dataclass(frozen=True)
class RokunoheMinutesThemeSourceChunk:
    """
    テーマ分析の入力に使うChroma DB上の六戸町会議録チャンク。

    Attributes:
        chroma_id: Chroma DB上のドキュメントID。
        document: チャンク本文。
        source: 出典PDFファイル名。
        source_date: 出典PDFファイル名から取得したYYYYMMDD形式の日付。
        page: PDF内のページ番号。
        chunk_index: RAG登録時のチャンク番号。
        embedding: K-meansクラスタリングに使うembeddingベクトル。
    """

    chroma_id: str
    document: str
    source: str
    source_date: str
    page: int | None
    chunk_index: int | None
    embedding: list[float]


@dataclass(frozen=True)
class RokunoheMinuteThemeChunkAnalysis:
    """
    テーマ分析でクラスタへ割り当てられた単一チャンクの分析結果。

    Attributes:
        source_chunk: 分析対象のChromaチャンク。
        candidate_labels: LLMがチャンク単位で抽出した候補テーマラベル。
        cluster_index: K-meansが割り当てたクラスタ番号。
    """

    source_chunk: RokunoheMinutesThemeSourceChunk
    candidate_labels: list[str]
    cluster_index: int


@dataclass(frozen=True)
class RokunoheMinuteThemeClusterAnalysis:
    """
    テーマ分析で生成されたクラスタ単位の分析結果。

    Service層で作る一時的なクラスタ集計VOです。Djangoモデルへ保存する前に、
    チャンク数、文字数、PDF数、source_date範囲をプロパティで算出し、
    RepositoryがそのままRokunoheMinuteThemeClusterへ移せる形にします。

    Attributes:
        cluster_index: K-meansが割り当てたクラスタ番号。
        label: LLMが命名した代表テーマ名。
        representative_chunk_id: クラスタを代表するChromaチャンクID。
        chunks: クラスタに属するチャンク分析結果。
    """

    cluster_index: int
    label: str
    representative_chunk_id: str
    chunks: list[RokunoheMinuteThemeChunkAnalysis]

    @property
    def chunk_count(self) -> int:
        return len(self.chunks)

    @property
    def character_count(self) -> int:
        return sum(len(chunk.source_chunk.document) for chunk in self.chunks)

    @property
    def pdf_count(self) -> int:
        return len({chunk.source_chunk.source for chunk in self.chunks})

    @property
    def source_date_from(self) -> str:
        dates = sorted(
            chunk.source_chunk.source_date
            for chunk in self.chunks
            if chunk.source_chunk.source_date
        )
        return dates[0] if dates else ""

    @property
    def source_date_to(self) -> str:
        dates = sorted(
            chunk.source_chunk.source_date
            for chunk in self.chunks
            if chunk.source_chunk.source_date
        )
        return dates[-1] if dates else ""
