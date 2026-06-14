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
    この日付は取り込み期間フィルタ、Chroma metadata、集計表示の直近1年判定で
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
    集計表示、出典表示はこのmetadataを前提に同じチャンクを追跡します。

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
class RokunoheMinutesStatsSourceChunk:
    """
    六戸町会議録collectionの集計に使うChroma DB上の本文チャンク。

    LLMやembeddingを使わず、本文と出典メタデータだけをPython側で集計するための
    入力VOです。頻出語ランキング、PDF別ボリューム、日付別ボリュームはこの
    チャンク集合から都度作ります。

    Attributes:
        chroma_id: Chroma DB上のドキュメントID。
        document: チャンク本文。
        source: 出典PDFファイル名。
        source_date: 出典PDFファイル名から取得したYYYYMMDD形式の日付。
        page: PDF内のページ番号。
        chunk_index: RAG登録時のチャンク番号。
    """

    chroma_id: str
    document: str
    source: str
    source_date: str
    page: int | None
    chunk_index: int | None


@dataclass(frozen=True)
class RokunoheMinutesWordFrequency:
    """
    六戸町会議録collectionから抽出した頻出語の集計結果。

    Attributes:
        word: Janomeで抽出した名詞または複合名詞。
        count: 対象チャンク全体での出現回数。
        pdf_count: その語が登場したPDF source数。
    """

    word: str
    count: int
    pdf_count: int


@dataclass(frozen=True)
class RokunoheMinutesSourceVolume:
    """
    PDF source単位の本文ボリューム集計結果。

    Attributes:
        source: 出典PDFファイル名。
        source_date: 出典PDFファイル名から取得したYYYYMMDD形式の日付。
        chunk_count: そのPDFから登録されたチャンク数。
        character_count: そのPDFから登録された本文文字数。
    """

    source: str
    source_date: str
    chunk_count: int
    character_count: int


@dataclass(frozen=True)
class RokunoheMinutesDateVolume:
    """
    source_date単位の本文ボリューム集計結果。

    Attributes:
        source_date: 出典PDFファイル名から取得したYYYYMMDD形式の日付。
        source_count: その日に含まれるPDF source数。
        chunk_count: その日に登録されたチャンク数。
        character_count: その日に登録された本文文字数。
    """

    source_date: str
    source_count: int
    chunk_count: int
    character_count: int


@dataclass(frozen=True)
class RokunoheMinutesCollectionStats:
    """
    六戸町会議録collectionをLLMなしで機械集計した表示用データ。

    1回のGETリクエストでChroma collectionから対象期間の本文チャンクを読み、
    Janomeの名詞抽出と単純な件数集計だけで作る軽量なスナップショットです。
    DBへ保存するジョブや途中状態は持ちません。

    Attributes:
        total_chunk_count: 集計対象のChromaチャンク数。
        total_character_count: 集計対象本文の総文字数。
        total_source_count: 集計対象PDF source数。
        word_frequencies: 頻出語ランキング。
        source_volumes: PDF source別ボリューム。
        date_volumes: source_date別ボリューム。
    """

    total_chunk_count: int
    total_character_count: int
    total_source_count: int
    word_frequencies: list[RokunoheMinutesWordFrequency]
    source_volumes: list[RokunoheMinutesSourceVolume]
    date_volumes: list[RokunoheMinutesDateVolume]
