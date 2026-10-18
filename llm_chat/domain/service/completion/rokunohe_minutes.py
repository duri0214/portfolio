import logging
import os
import re
import unicodedata
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from django.contrib.auth.models import User
from django.utils import timezone
from janome.tokenizer import Tokenizer
from lib.llm.valueobject.completion import RoleType
from pypdf import PdfReader

from lib.llm.valueobject.config import ModelDefaults, OpenAIGptConfig
from llm_chat.domain.repository.completion.rokunohe_minutes import (
    RokunoheMinutesRagRepository,
)
from llm_chat.domain.service.completion.base import BaseChatService
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.rokunohe_minutes import (
    RokunoheMinutesCollectionStats,
    RokunoheMinutesDateVolume,
    RokunoheMinutesDocument,
    RokunoheMinutesImportStatus,
    RokunoheMinutesMetadata,
    RokunoheMinutesPdf,
    RokunoheMinutesPdfIndex,
    RokunoheMinutesSourceVolume,
    RokunoheMinutesStatsSourceChunk,
    RokunoheMinutesWordFrequency,
)
from llm_chat.domain.valueobject.completion.use_case import UseCaseType

logger = logging.getLogger(__name__)


class RokunoheMinutesPdfIndexService:
    """
    六戸町公式サイトのHTMLから会議録PDFリンクだけを一覧化するService。

    Attributes:
        target_urls: 会議録の現行ページとバックナンバーページのURL。
    """

    target_urls = (
        "https://www.town.rokunohe.aomori.jp/docs/2023051900005/",
        "https://www.town.rokunohe.aomori.jp/docs/2023051900005/"
        "chousei_cyougikai_kaigiroku_kako.html",
    )

    def list_pdfs(
        self,
        *,
        held_on_from: int | None = None,
        held_on_to: int | None = None,
    ) -> list[RokunoheMinutesPdfIndex]:
        """
        現行ページとバックナンバーページのHTMLだけを取得してPDFリンクを返します。

        PDF本体、Chroma DB、OpenAI APIにはアクセスしません。リンクが重複している場合は
        URL単位で1件にまとめ、公式ページの掲載順を維持します。開催日が見出しとリンク表示から取得できるPDFは、
        held_on_from/toで指定された範囲に絞り込みます。
        """
        pdfs_by_url: dict[str, RokunoheMinutesPdfIndex] = {}
        for target_url in self.target_urls:
            response = requests.get(target_url, timeout=30)
            response.raise_for_status()
            response.encoding = response.apparent_encoding
            soup = BeautifulSoup(response.text, "html.parser")
            for pdf in self._find_pdf_links(soup.find_all("a"), target_url):
                pdfs_by_url.setdefault(pdf.url, pdf)
        pdfs = [
            pdf
            for pdf in pdfs_by_url.values()
            if self._is_within_held_on_range(
                pdf,
                held_on_from=held_on_from,
                held_on_to=held_on_to,
            )
        ]
        return pdfs

    @staticmethod
    def _find_pdf_links(links, target_url: str) -> list[RokunoheMinutesPdfIndex]:
        pdf_links = []
        for link in links:
            href = link.get("href")
            if not href:
                continue

            text = link.get_text()
            if ".pdf" not in href.lower() and "[pdf" not in text.lower():
                continue

            filename = RokunoheMinutesPdfIndexService._get_filename(text, href)
            if not filename.lower().endswith(".pdf"):
                filename += ".pdf"
            title = RokunoheMinutesPdfIndexService._get_title(text)
            era_year, calendar_year = RokunoheMinutesPdfIndexService._get_year(link)
            meeting_label = RokunoheMinutesPdfIndexService._get_meeting_label(link)
            month, day = RokunoheMinutesPdfIndexService._get_held_on(title)
            pdf_links.append(
                RokunoheMinutesPdfIndex(
                    filename=filename,
                    url=urljoin(
                        RokunoheMinutesPdfIndexService._get_base_url(target_url), href
                    ),
                    title=title,
                    era_year=era_year,
                    calendar_year=calendar_year,
                    category=RokunoheMinutesPdfIndexService._get_category(title),
                    meeting_label=meeting_label,
                    month=month,
                    day=day,
                )
            )
        return pdf_links

    @staticmethod
    def _is_within_held_on_range(
        pdf: RokunoheMinutesPdfIndex,
        *,
        held_on_from: int | None,
        held_on_to: int | None,
    ) -> bool:
        if held_on_from is None and held_on_to is None:
            return True
        if not (pdf.calendar_year and pdf.month and pdf.day):
            return False

        held_on = pdf.calendar_year * 10000 + pdf.month * 100 + pdf.day
        if held_on_from is not None and held_on < held_on_from:
            return False
        return held_on_to is None or held_on <= held_on_to

    @staticmethod
    def _get_base_url(target_url: str) -> str:
        if target_url.endswith("/") or target_url.endswith(".html"):
            return target_url
        return f"{target_url}/"

    @staticmethod
    def _get_filename(text: str, href: str) -> str:
        filename = re.sub(r"\[pdf.*?]", "", text, flags=re.IGNORECASE).strip()
        filename = re.sub(r'[\\/:*?"<>|]', "_", filename)
        filename = re.sub(r"\s+", "_", filename)
        return filename or Path(href).name

    @staticmethod
    def _get_title(text: str) -> str:
        normalized_text = unicodedata.normalize("NFKC", text)
        title = re.sub(r"\[pdf.*?]", "", normalized_text, flags=re.IGNORECASE)
        normalized_title = re.sub(r"\s+", " ", title).strip()
        return normalized_title.replace("(", "（").replace(")", "）") or "会議録名不明"

    @staticmethod
    def _get_year(link) -> tuple[str, int | None]:
        for heading in link.find_all_previous(["h1", "h2", "h3", "h4", "h5", "h6"]):
            heading_text = unicodedata.normalize(
                "NFKC", heading.get_text(" ", strip=True)
            )
            reiwa_match = re.search(r"令和\s*(\d+)\s*年", heading_text)
            if reiwa_match:
                era_number = int(reiwa_match.group(1))
                return f"令和{era_number}年", 2018 + era_number

            heisei_match = re.search(r"平成\s*(\d+)\s*年", heading_text)
            if heisei_match:
                era_number = int(heisei_match.group(1))
                return f"平成{era_number}年", 1988 + era_number
        return "", None

    @staticmethod
    def _get_meeting_label(link) -> str:
        for element in link.find_all_previous(
            ["h1", "h2", "h3", "h4", "h5", "h6", "p", "li"]
        ):
            label = unicodedata.normalize("NFKC", element.get_text(" ", strip=True))
            if re.search(r"第\s*\d+\s*回(?:定例会|臨時会)", label):
                return label.replace("[", "［").replace("]", "］")
        return ""

    @staticmethod
    def _get_held_on(title: str) -> tuple[int | None, int | None]:
        held_on_match = re.search(r"(\d+)月\s*(\d+)日", title)
        if not held_on_match:
            return None, None
        return int(held_on_match.group(1)), int(held_on_match.group(2))

    @staticmethod
    def _get_category(title: str) -> str:
        category = re.split(r"[（(]", title, maxsplit=1)[0].strip()
        return re.sub(r"本会議\s*\d+号$", "本会議", category) or "その他"


class RokunoheMinutesPdfImportService:
    """
    単一PDFファイルを六戸町会議録RAGへ登録するための取り込みパイプライン。

    このServiceは、管理コマンドが保存した1つのPDFを入力にして、以下の順で
    RAG登録可否を判断します。

    1. ファイル名先頭のYYYYMMDDを読み取り、指定された処理期間外なら読み取り前にスキップする。
    2. 同じPDF sourceがChroma DBへ登録済みなら、再登録せずスキップする。
    3. PDFをページ単位で読み取り、本文があるページだけRAG登録用ドキュメントへ変換する。
    4. 同一PDF由来の既存チャンクを削除してから、最新のページ本文をChroma DBへ登録する。

    Chroma DBの存在確認、削除、登録はRepositoryへ委譲します。このServiceは
    「単一PDFをどの状態として扱うか」というフロー制御と、PDF本文から
    RokunoheMinutesDocumentを作る責務だけを持ちます。
    """

    default_recent_days = 365

    def __init__(
        self,
        repository: RokunoheMinutesRagRepository | None = None,
        *,
        recent_days: int | None = None,
        source_date_from: int | None = None,
        source_date_to: int | None = None,
    ) -> None:
        """
        六戸町会議録PDFインポートServiceを初期化します。

        Args:
            repository: Chroma DBへの登録済み確認とドキュメント登録を担当するRepository。
                テスト時はモックRepositoryを渡し、本番時は未指定のまま環境変数のAPIキーを使って生成します。
            recent_days: 取り込み対象にする直近日数。未指定時は365日です。
            source_date_from: 取り込み対象にするPDF日付の下限。YYYYMMDD形式です。
            source_date_to: 取り込み対象にするPDF日付の上限。YYYYMMDD形式です。
        """
        self.recent_days = recent_days or self.default_recent_days
        self.source_date_from = source_date_from
        self.source_date_to = source_date_to
        self.repository = repository or RokunoheMinutesRagRepository(
            api_key=os.getenv("OPENAI_API_KEY") or ""
        )

    def import_pdf(self, pdf_path: Path) -> RokunoheMinutesImportStatus:
        """
        単一PDFを処理期間判定、重複判定、本文抽出、Chroma登録の順に通します。

        Args:
            pdf_path: ローカルに保存済みの六戸町会議録PDFファイルパス。

        Returns:
            RokunoheMinutesImportStatus:
                - IMPORTED: PDF本文を抽出し、Chroma DBへ登録した。
                - SKIPPED_EXISTING: 同じsource名のPDFが登録済みだった。
                - SKIPPED_OUT_OF_SOURCE_DATE_RANGE: PDFの日付が取り込み対象期間外だった。
                - SKIPPED_EMPTY_TEXT: PDFから登録可能な本文を抽出できなかった。

        Side Effects:
            未登録かつ本文抽出に成功した場合だけ、Repository経由で同一PDF由来の
            既存ドキュメントを削除し、新しいページ単位ドキュメントをChroma DBへ登録します。
            期間外、登録済み、本文なしの場合はChroma DBを変更しません。
        """
        pdf = RokunoheMinutesPdf(path=pdf_path)
        if self._is_out_of_source_date_range(pdf):
            return RokunoheMinutesImportStatus.SKIPPED_OUT_OF_SOURCE_DATE_RANGE

        if self.repository.exists(pdf):
            return RokunoheMinutesImportStatus.SKIPPED_EXISTING

        documents = self._create_documents(pdf)
        if not documents:
            return RokunoheMinutesImportStatus.SKIPPED_EMPTY_TEXT

        self.repository.delete_pdf_documents(pdf)
        self.repository.upsert_documents(documents)
        return RokunoheMinutesImportStatus.IMPORTED

    def get_source_date_from(self) -> int:
        """
        PDF取り込み対象期間の下限日付をYYYYMMDD整数で返します。

        明示的なsource_date_fromが指定されていればそれを優先し、未指定なら
        今日からrecent_days日前を下限にします。管理画面からの通常実行では
        source_date_from未指定のため、直近1年が処理基準になります。
        """
        if self.source_date_from is not None:
            return self.source_date_from
        recent_start = timezone.localdate() - timedelta(days=self.recent_days)
        return int(recent_start.strftime("%Y%m%d"))

    def _is_out_of_source_date_range(self, pdf: RokunoheMinutesPdf) -> bool:
        """
        PDFファイル名の日付が取り込み対象期間外かを判定します。

        ファイル名にYYYYMMDDプレフィックスがないPDFは、日付判定できないため
        期間外扱いにはしません。日付がある場合は下限未満、または上限指定時の
        上限超過を対象期間外として扱います。
        """
        if not pdf.source_date:
            return False
        source_date = int(pdf.source_date)
        if source_date < self.get_source_date_from():
            return True
        return self.source_date_to is not None and source_date > self.source_date_to

    @staticmethod
    def _create_documents(pdf: RokunoheMinutesPdf) -> list[RokunoheMinutesDocument]:
        """
        PDFをページ単位で読み、RAG登録用ドキュメントへ変換します。

        PDF全体を1つの長文として扱うのではなく、ページ単位のチャンクとして
        Chroma DBへ登録します。ページ番号とchunk_indexをメタデータへ入れることで、
        後続のコレクションビューア、集計表示、出典表示が同じ粒度で追跡できます。

        Args:
            pdf: 本文抽出対象の六戸町会議録PDF。

        Returns:
            list[RokunoheMinutesDocument]:
                ページ単位の抽出本文とsource/page/dateメタデータを持つドキュメント。
                PDFから空文字しか得られない場合は空リストを返します。

        Side Effects:
            PDFファイルを読み取り、各ページからテキストを抽出します。
        """
        reader = PdfReader(pdf.path)
        documents = []
        for page_index, page in enumerate(reader.pages, start=1):
            text = page.extract_text()
            if not text or not text.strip():
                continue

            metadata = RokunoheMinutesMetadata.from_pdf(
                pdf,
                page=page_index,
                chunk_index=page_index - 1,
            )
            documents.append(
                RokunoheMinutesDocument(
                    page_content=text.strip(),
                    metadata=metadata.to_dict(),
                )
            )

        return documents


class RokunoheMinutesRagService(BaseChatService):
    """
    登録済み六戸町会議録collectionを使ってチャット回答を生成するService。

    このServiceは、PDF取り込み済みの `rokunohe_minutes` collection を前提に、
    ユーザー質問を以下のパイプラインでassistantメッセージへ変換します。

    1. UseCase層から受け取ったMessageDTOをRepositoryが扱うMessageへ変換する。
    2. RepositoryにChroma DB検索とLLM回答生成を委譲する。
    3. 返ってきた回答本文を、チャット履歴へ保存可能なassistant MessageDTOへ詰め直す。

    ChatLogsへの保存責務はUseCase層に残し、このServiceは「RAG回答を作る」
    ところまでに責務を限定します。

    Attributes:
        model_name: 六戸町会議録RAG回答生成に使用するLLMモデル名。
    """

    model_name = ModelDefaults.ROKUNOHE_MINUTES_RAG.model
    collection_summary_marker = "<!-- rokunohe-collection-summary -->"
    initial_summary_prompt = (
        "取り込み済みの六戸町会議録を横断して、分析の入口になる初回サマリーを作成してください。"
        "主要テーマ、直近の傾向、深掘りに向く質問例を日本語で簡潔に箇条書きしてください。"
        "根拠にした会議録の出典も分かる範囲で添えてください。"
    )

    def __init__(self, repository: RokunoheMinutesRagRepository | None = None):
        """
        六戸町会議録RAG回答生成Serviceを初期化します。

        Args:
            repository: RAG検索と回答生成を担当するRepository。
                テスト時はモックRepositoryを渡し、本番時は未指定のままOpenAI設定から生成します。
        """
        super().__init__(model_name=self.model_name)
        self.config = OpenAIGptConfig.from_profile(
            ModelDefaults.ROKUNOHE_MINUTES_RAG,
            api_key=os.getenv("OPENAI_API_KEY") or "",
            max_tokens=4000,
        )
        self.repository = repository or RokunoheMinutesRagRepository(
            api_key=self.config.api_key,
            model=self.config.model,
        )

    def generate(self, user_message: MessageDTO) -> MessageDTO:
        """
        ユーザー質問に対する六戸町会議録RAG回答を生成します。

        Args:
            user_message: ユーザーの質問内容を持つMessageDTO。

        Returns:
            MessageDTO:
                Repositoryが返したRAG回答本文をcontentに持つassistantメッセージ。

        Side Effects:
            Repository経由でChroma DB検索とLLM回答生成を行います。
            このメソッド自体はChatLogsへの保存を行わず、保存はUseCase層が担当します。
        """
        response = self.repository.retrieve_answer(user_message.to_message())

        return self._create_assistant_message(
            user=user_message.user,
            content=response.answer,
            use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
        )

    def generate_initial_summary(self, user: User) -> MessageDTO:
        """
        PDF取り込み直後に表示する分析入口用サマリーを生成します。

        PDF取得・ベクトル化後はユーザー質問がまだ存在しないため、固定プロンプトを
        仮のユーザーメッセージとして流し、取り込み済みcollectionの主要テーマや
        深掘り質問例を先に提示します。戻り値の保存は呼び出し元のViewが担当します。

        Args:
            user: サマリーを保存する対象ユーザー。

        Returns:
            MessageDTO: チャット履歴へ保存するassistantメッセージ。
        """
        collection_scope = self._build_collection_scope_label()
        user_message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=self.initial_summary_prompt,
            model_name=self.model_name,
            use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
        )
        summary = self.generate(user_message)
        return self._create_assistant_message(
            user=user,
            content=(
                f"{self.collection_summary_marker}\n"
                "### コレクションサマリー\n\n"
                f"> 検索対象: {collection_scope}\n"
                "> このサマリーは関連する会議録チャンクの検索結果をもとに作成しています。\n\n"
                f"{summary.content}"
            ),
            use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
        )

    def _build_collection_scope_label(self) -> str:
        """初回サマリー生成時点の登録済み会議録の範囲を表示用テキストにします。"""
        chunks = self.repository.list_stats_source_chunks()
        sources = {chunk.source for chunk in chunks if chunk.source}
        source_dates = sorted(
            {
                chunk.source_date
                for chunk in chunks
                if re.fullmatch(r"\d{8}", chunk.source_date)
            }
        )
        undated_sources = {
            chunk.source
            for chunk in chunks
            if chunk.source and not re.fullmatch(r"\d{8}", chunk.source_date)
        }
        if not sources:
            return "登録済み会議録なし"
        if not source_dates:
            return f"登録済み会議録全体（PDF: {len(sources)}件、PDF更新日不明）"

        details = (
            f"PDF更新日: {self._format_source_date(source_dates[0])}〜"
            f"{self._format_source_date(source_dates[-1])}、PDF: {len(sources)}件"
        )
        if undated_sources:
            details += f"、PDF更新日不明: {len(undated_sources)}件"
        return f"登録済み会議録全体（{details}）"

    @staticmethod
    def _format_source_date(source_date: str) -> str:
        """YYYYMMDD形式のPDF更新日を画面表示用に整形します。"""
        return f"{source_date[:4]}-{source_date[4:6]}-{source_date[6:]}"


class RokunoheMinutesCollectionStatsService:
    """
    六戸町会議録collectionをLLMなしで頻出語・ボリューム集計するService。

    このServiceは、Chroma DBに保存済みの本文チャンクを読み取り、Janomeで名詞と
    複合名詞を抽出して頻出語ランキングを作ります。K-means、LLM、Django DB保存は
    行わず、GETリクエスト時にその場で集計結果VOを返します。

    処理は次の順で進みます。

    1. 直近1年分、または画面で指定されたsource_date範囲のChromaチャンクを取得する。
    2. チャンク本文をJanomeで形態素解析し、名詞が連続する部分は複合名詞として扱う。
    3. ストップワード、1文字語、数字だけの語、議事録の定型語を除外する。
    4. 頻出語、PDF source別ボリューム、source_date別ボリュームをメモリ上で集計する。

    Attributes:
        default_recent_days: 期間未指定時に集計対象にする直近日数。
        default_word_limit: 頻出語ランキングの既定表示件数。
    """

    default_recent_days = 365
    default_word_limit = 50
    stop_words = {
        "こと",
        "もの",
        "ため",
        "ところ",
        "これ",
        "それ",
        "ここ",
        "よう",
        "さん",
        "議長",
        "委員",
        "町長",
        "課長",
        "部長",
        "議員",
        "答弁",
        "質問",
        "説明",
        "会議",
        "本会議",
        "委員会",
        "六戸町",
        "ページ",
        "発言",
        "資料",
        "以上",
        "次第",
        "今回",
        "現在",
        "関係",
        "お願い",
        "確認",
        "対応",
        "考え",
    }
    number_pattern = re.compile(r"^[0-9０-９]+$")

    def __init__(
        self,
        *,
        rag_repository: RokunoheMinutesRagRepository | None = None,
        source_date_from: int | None = None,
        source_date_to: int | None = None,
        word_limit: int | None = None,
    ) -> None:
        self.rag_repository = rag_repository or RokunoheMinutesRagRepository(
            api_key=os.getenv("OPENAI_API_KEY") or ""
        )
        self.source_date_from = source_date_from
        self.source_date_to = source_date_to
        self.word_limit = word_limit or self.default_word_limit
        self.tokenizer = Tokenizer()

    def build_stats(self) -> RokunoheMinutesCollectionStats:
        """
        対象期間内のChromaチャンクから集計結果を作ります。

        Returns:
            RokunoheMinutesCollectionStats:
                頻出語ランキング、PDF別ボリューム、日付別ボリュームを持つ表示用VO。

        Side Effects:
            Chroma DBから本文とmetadataを読み取ります。LLM API呼び出しやDjango DB保存は
            行いません。
        """
        source_date_from = self._get_source_date_from()
        source_date_to = self.source_date_to
        chunks = self.rag_repository.list_stats_source_chunks(
            source_date_from=source_date_from,
            source_date_to=source_date_to,
        )
        logger.info(
            "Rokunohe collection stats started: chunks=%s source_date_from=%s source_date_to=%s",
            len(chunks),
            source_date_from,
            source_date_to or "指定なし",
        )
        word_counts = Counter()
        word_sources: dict[str, set[str]] = defaultdict(set)
        source_counts: dict[str, dict[str, int | str]] = {}
        date_counts: dict[str, dict[str, int | set[str]]] = {}

        for chunk in chunks:
            character_count = len(chunk.document)
            source_key = chunk.source or "出典不明"
            date_key = chunk.source_date or "日付不明"
            source_stats = source_counts.setdefault(
                source_key,
                {
                    "source": source_key,
                    "source_date": chunk.source_date,
                    "chunk_count": 0,
                    "character_count": 0,
                },
            )
            source_stats["chunk_count"] = int(source_stats["chunk_count"]) + 1
            source_stats["character_count"] = (
                int(source_stats["character_count"]) + character_count
            )

            date_stats = date_counts.setdefault(
                date_key,
                {
                    "source_date": date_key,
                    "sources": set(),
                    "chunk_count": 0,
                    "character_count": 0,
                },
            )
            sources = date_stats["sources"]
            if isinstance(sources, set):
                sources.add(source_key)
            date_stats["chunk_count"] = int(date_stats["chunk_count"]) + 1
            date_stats["character_count"] = (
                int(date_stats["character_count"]) + character_count
            )

            chunk_words = self._extract_words(chunk.document)
            word_counts.update(chunk_words)
            for word in set(chunk_words):
                word_sources[word].add(source_key)

        word_frequencies = [
            RokunoheMinutesWordFrequency(
                word=word,
                count=count,
                pdf_count=len(word_sources[word]),
            )
            for word, count in word_counts.most_common(self.word_limit)
        ]
        source_volumes = self._build_source_volumes(source_counts)
        date_volumes = self._build_date_volumes(date_counts)
        total_character_count = sum(len(chunk.document) for chunk in chunks)
        logger.info(
            "Rokunohe collection stats completed: chunks=%s words=%s sources=%s dates=%s",
            len(chunks),
            len(word_frequencies),
            len(source_volumes),
            len(date_volumes),
        )
        return RokunoheMinutesCollectionStats(
            total_chunk_count=len(chunks),
            total_character_count=total_character_count,
            total_source_count=len({chunk.source for chunk in chunks if chunk.source}),
            word_frequencies=word_frequencies,
            source_volumes=source_volumes,
            date_volumes=date_volumes,
        )

    def _get_source_date_from(self) -> int:
        """
        集計対象の下限日付をYYYYMMDD整数で返します。

        通常表示ではビューアと同じ直近1年を使います。画面の期間指定で
        source_date_fromが明示された場合は、その日付を優先して短い範囲だけを
        集計できるようにします。
        """
        if self.source_date_from is not None:
            return self.source_date_from
        recent_start = timezone.localdate() - timedelta(days=self.default_recent_days)
        return int(recent_start.strftime("%Y%m%d"))

    def _extract_words(self, text: str) -> list[str]:
        """
        Janomeで本文から名詞または複合名詞を抽出します。

        名詞が連続する場合は「学校」「給食」ではなく「学校給食」として扱います。
        ただし長すぎる複合語は議事録の固有表現や読み取りノイズになりやすいため、
        30文字で打ち切ってからフィルタします。
        """
        words = []
        noun_parts = []
        for token in self.tokenizer.tokenize(text):
            part_of_speech = token.part_of_speech.split(",")
            surface = token.surface.strip()
            if self._is_collectable_noun(part_of_speech, surface):
                noun_parts.append(surface)
                continue
            words.extend(self._flush_noun_parts(noun_parts))
            noun_parts = []
        words.extend(self._flush_noun_parts(noun_parts))
        return words

    def _flush_noun_parts(self, noun_parts: list[str]) -> list[str]:
        if not noun_parts:
            return []
        word = "".join(noun_parts)[:30]
        return [word] if self._should_keep_word(word) else []

    def _is_collectable_noun(self, part_of_speech: list[str], surface: str) -> bool:
        if not surface:
            return False
        if len(part_of_speech) < 2:
            return False
        if part_of_speech[0] != "名詞":
            return False
        if part_of_speech[1] in {"数", "代名詞", "非自立"}:
            return False
        return True

    def _should_keep_word(self, word: str) -> bool:
        normalized = word.strip()
        if len(normalized) <= 1:
            return False
        if normalized in self.stop_words:
            return False
        if self.number_pattern.match(normalized):
            return False
        return True

    @staticmethod
    def _build_source_volumes(
        source_counts: dict[str, dict[str, int | str]],
    ) -> list[RokunoheMinutesSourceVolume]:
        return [
            RokunoheMinutesSourceVolume(
                source=str(stats["source"]),
                source_date=str(stats["source_date"]),
                chunk_count=int(stats["chunk_count"]),
                character_count=int(stats["character_count"]),
            )
            for stats in sorted(
                source_counts.values(),
                key=lambda item: (-int(item["character_count"]), str(item["source"])),
            )
        ]

    @staticmethod
    def _build_date_volumes(
        date_counts: dict[str, dict[str, int | set[str]]],
    ) -> list[RokunoheMinutesDateVolume]:
        volumes = []
        for stats in sorted(
            date_counts.values(),
            key=lambda item: str(item["source_date"]),
            reverse=True,
        ):
            sources = stats["sources"]
            source_count = len(sources) if isinstance(sources, set) else 0
            volumes.append(
                RokunoheMinutesDateVolume(
                    source_date=str(stats["source_date"]),
                    source_count=source_count,
                    chunk_count=int(stats["chunk_count"]),
                    character_count=int(stats["character_count"]),
                )
            )
        return volumes
