import logging
import os
import re
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path

from django.contrib.auth.models import User
from django.utils import timezone
from janome.tokenizer import Tokenizer
from lib.llm.valueobject.completion import RoleType
from pypdf import PdfReader

from lib.llm.valueobject.config import OpenAIGptConfig, ModelName
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
    RokunoheMinutesSourceVolume,
    RokunoheMinutesStatsSourceChunk,
    RokunoheMinutesWordFrequency,
)
from llm_chat.domain.valueobject.completion.use_case import UseCaseType

logger = logging.getLogger(__name__)


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

    model_name = ModelName.GPT_5_MINI
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
        self.config = OpenAIGptConfig(
            api_key=os.getenv("OPENAI_API_KEY") or "",
            max_tokens=4000,
            model=self.model_name,
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
        user_message = MessageDTO(
            user=user,
            role=RoleType.USER,
            content=self.initial_summary_prompt,
            model_name=self.model_name,
            use_case_type=UseCaseType.ROKUNOHE_MINUTES_RAG,
        )
        return self.generate(user_message)


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
