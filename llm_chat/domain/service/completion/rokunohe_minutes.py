import logging
import os
from datetime import timedelta
from pathlib import Path

from django.contrib.auth.models import User
from django.utils import timezone
from lib.llm.valueobject.completion import RoleType
import numpy as np
from openai import OpenAI
from pypdf import PdfReader

from lib.llm.valueobject.config import OpenAIGptConfig, ModelName
from llm_chat.domain.repository.completion.rokunohe_minutes import (
    RokunoheMinutesRagRepository,
)
from llm_chat.domain.repository.completion.rokunohe_minutes_theme import (
    RokunoheMinuteThemeAnalysisRepository,
)
from llm_chat.domain.service.completion.base import BaseChatService
from llm_chat.domain.valueobject.completion.chat import MessageDTO
from llm_chat.domain.valueobject.completion.rokunohe_minutes import (
    RokunoheMinuteThemeChunkAnalysis,
    RokunoheMinuteThemeClusterAnalysis,
    RokunoheMinutesDocument,
    RokunoheMinutesImportStatus,
    RokunoheMinutesMetadata,
    RokunoheMinutesPdf,
    RokunoheMinutesThemeSourceChunk,
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
        後続のコレクションビューア、テーマ分析、出典表示が同じ粒度で追跡できます。

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


class RokunoheMinuteThemeLabelService:
    """
    テーマ分析パイプライン内でLLMによるラベル生成だけを担当するService。

    テーマ分析は、embeddingによる機械的なクラスタリングだけでは人間が読める
    テーマ名にならないため、LLMを2段階で使います。

    1. 各チャンク本文から、政策テーマを表す短い候補ラベルを最大5件抽出する。
    2. 同じクラスタに属する候補ラベルと本文抜粋を束ね、代表テーマ名を1つ生成する。

    Chroma DBやDjango DBには触れず、LLM入出力の整形だけをこのServiceに閉じ込めます。

    Attributes:
        model_name: テーマ候補と代表ラベル生成に使用するLLMモデル名。
    """

    model_name = ModelName.GPT_5_MINI

    def __init__(self, *, api_key: str | None = None) -> None:
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY") or "")

    def extract_candidate_labels(self, text: str) -> list[str]:
        """
        単一チャンク本文から政策テーマ候補ラベルを抽出します。

        クラスタリングの前処理として、各チャンクに人間が読める短い
        テーマ候補を付与します。この時点ではクラスタ代表名ではなく、
        後続のクラスタ命名で使う素材を作るだけです。

        Args:
            text: 六戸町会議録チャンク本文。

        Returns:
            list[str]: 最大5件の候補テーマラベル。
        """
        prompt = (
            "以下の六戸町会議録本文から、政策テーマを表す短い日本語ラベルを最大5件抽出してください。"
            "回答は1行1ラベルにしてください。\n\n"
            f"{text[:3000]}"
        )
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content or ""
        return self._parse_labels(content)

    def name_cluster(self, chunks: list[RokunoheMinuteThemeChunkAnalysis]) -> str:
        """
        クラスタに属するチャンク群から代表テーマ名を生成します。

        K-meansで同じクラスタに割り当てられたチャンクの候補ラベルと本文抜粋を
        LLMへ渡し、ビューアで一覧しやすい20文字以内の名詞句へ圧縮します。
        保存時はRokunoheMinuteThemeClusterのlabelになります。

        Args:
            chunks: 同一クラスタに属するチャンク分析結果。

        Returns:
            str: クラスタ代表テーマ名。
        """
        label_text = "\n".join(
            f"- {label}"
            for chunk in chunks[:20]
            for label in chunk.candidate_labels[:5]
        )
        excerpt_text = "\n".join(
            f"- {chunk.source_chunk.document[:200]}" for chunk in chunks[:5]
        )
        prompt = (
            "以下の候補ラベルと本文抜粋をもとに、クラスタの代表テーマ名を"
            "日本語で20文字以内の名詞句1つにしてください。\n\n"
            f"候補ラベル:\n{label_text}\n\n本文抜粋:\n{excerpt_text}"
        )
        response = self.client.chat.completions.create(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content or ""
        label = content.strip().splitlines()[0].strip(" -・#")
        return label[:255] or "未分類テーマ"

    @staticmethod
    def _parse_labels(content: str) -> list[str]:
        labels = []
        for line in content.splitlines():
            label = line.strip().lstrip("-*0123456789.、)） ").strip()
            if label and label not in labels:
                labels.append(label[:100])
            if len(labels) >= 5:
                break
        return labels


class RokunoheMinuteThemeAnalysisService:
    """
    六戸町会議録RAGの既存チャンクからテーマ分析結果を作る集計パイプライン。

    このServiceは、既にChroma DBへ登録された会議録チャンクを入力にして、
    ビューアや後続分析で参照できるテーマクラスタをDjango DBへ保存します。
    Chroma DBは本文、メタデータ、embeddingの取得元に限定し、集計結果の正本は
    RokunoheMinuteThemeAnalysisRepository経由でDjango DBへ置きます。

    処理は次の順で進みます。

    1. 直近1年分、またはデバッグ用に指定されたsource_date範囲のChromaチャンクを取得する。
    2. 完了/失敗済みの保存済みテーマ分析結果を削除する。
    3. 既存runningジョブがあればfailedへ畳み、前回中断や二重送信の残骸を中断扱いにする。
    4. 新しい分析ジョブをrunning状態で作成し、以降の保存先として固定する。
    5. embeddingをK-meansでクラスタリングし、各チャンクへcluster_indexを付与する。
    6. 各チャンク本文をLLMへ渡して候補テーマラベルを抽出する。
    7. クラスタごとに候補ラベルと本文抜粋をLLMへ渡し、代表テーマ名を生成する。
    8. クラスタ、チャンク紐づけ、候補ラベルをDjango DBへ保存し、ジョブをcompletedへ更新する。
    9. 途中で失敗した場合はジョブをfailedへ更新し、例外を呼び出し元へ再送出する。

    Vector DBは集計や履歴管理が得意ではないため、テーマ分析結果はVector DBへ
    積み増さず、毎回Django DB上で作り直します。

    Attributes:
        default_cluster_count: 通常実行時に生成を試みるクラスタ数。
        default_recent_days: テーマ分析対象にする直近日数。
        random_state: K-means再現性のために固定する乱数シード。
    """

    default_cluster_count = 50
    default_recent_days = 365
    random_state = 42

    def __init__(
        self,
        *,
        rag_repository: RokunoheMinutesRagRepository | None = None,
        theme_repository: RokunoheMinuteThemeAnalysisRepository | None = None,
        label_service: RokunoheMinuteThemeLabelService | None = None,
        source_date_from: int | None = None,
        source_date_to: int | None = None,
    ) -> None:
        self.rag_repository = rag_repository or RokunoheMinutesRagRepository(
            api_key=os.getenv("OPENAI_API_KEY") or ""
        )
        self.theme_repository = (
            theme_repository or RokunoheMinuteThemeAnalysisRepository()
        )
        self.label_service = label_service or RokunoheMinuteThemeLabelService()
        self.source_date_from = source_date_from
        self.source_date_to = source_date_to

    def run(self):
        """
        対象期間内のChromaチャンクから最新のテーマ分析ジョブを作成します。

        このメソッドはテーマ分析の入口であり、途中状態をまたいで複数の
        Repository/LLM処理を連結します。呼び出し元のViewはこのメソッドを1回呼ぶだけで、
        「分析対象取得、既存結果リセット、既存runningのfailed化、ジョブ作成、
        クラスタリング、LLMラベル生成、DB保存、完了/失敗ステータス更新」までを
        一括実行します。

        空のcollectionや対象期間内に分析対象チャンクがない場合は、分析ジョブを作らず
        ValueErrorを送出します。ジョブ作成後の失敗は、failed状態へ更新してから
        例外を再送出します。

        Returns:
            RokunoheMinuteThemeAnalysisJob: 完了状態に更新された分析ジョブ。

        Side Effects:
            Chroma DBからチャンクとembeddingを取得し、LLM APIを呼び出して候補ラベルと
            クラスタ代表ラベルを生成し、保存済みテーマ分析結果をリセットし、
            残っているrunningジョブをfailedへ畳んでからDjango DBへ分析結果を保存します。
        """
        source_date_from = self._get_source_date_from()
        source_date_to = self.source_date_to
        chunks = self.rag_repository.list_theme_source_chunks(
            source_date_from=source_date_from,
            source_date_to=source_date_to,
        )
        if not chunks:
            raise ValueError(
                "rokunohe_minutes collection に対象期間内の分析対象がありません。"
            )

        logger.info(
            "Rokunohe theme analysis started: chunks=%s source_date_from=%s source_date_to=%s",
            len(chunks),
            source_date_from,
            source_date_to or "指定なし",
        )
        deleted_count = self.theme_repository.reset_analysis_results()
        failed_running_count = self.theme_repository.mark_running_jobs_failed()
        logger.info(
            "Rokunohe theme analysis previous jobs prepared: deleted=%s failed_running=%s",
            deleted_count,
            failed_running_count,
        )
        job = self.theme_repository.create_job(
            requested_cluster_count=self.default_cluster_count,
            llm_model_name=self.label_service.model_name,
        )
        logger.info("Rokunohe theme analysis job created: job_id=%s", job.pk)
        try:
            chunk_analyses = self._create_chunk_analyses(chunks)
            cluster_analyses = self._create_cluster_analyses(chunk_analyses)
            logger.info(
                "Rokunohe theme analysis saving results: job_id=%s clusters=%s chunks=%s",
                job.pk,
                len(cluster_analyses),
                len(chunk_analyses),
            )
            self.theme_repository.save_analysis_result(
                job=job,
                clusters=cluster_analyses,
            )
            completed_job = self.theme_repository.mark_completed(
                job=job,
                chunk_count=len(chunk_analyses),
                actual_cluster_count=len(cluster_analyses),
            )
            logger.info(
                "Rokunohe theme analysis completed: job_id=%s clusters=%s chunks=%s",
                job.pk,
                completed_job.actual_cluster_count,
                completed_job.chunk_count,
            )
            return completed_job
        except Exception as e:
            self.theme_repository.mark_failed(job=job, error_message=str(e))
            logger.exception("Rokunohe theme analysis failed: job_id=%s", job.pk)
            raise

    def _get_source_date_from(self) -> int:
        """
        テーマ分析対象の下限日付をYYYYMMDD整数で返します。

        通常実行ではビューアと同じ直近1年を使います。画面のデバッグ期間で
        source_date_fromが明示された場合は、その日付を優先して短い範囲だけを
        分析できるようにします。
        """
        if self.source_date_from is not None:
            return self.source_date_from
        recent_start = timezone.localdate() - timedelta(days=self.default_recent_days)
        return int(recent_start.strftime("%Y%m%d"))

    def _create_chunk_analyses(
        self,
        chunks: list[RokunoheMinutesThemeSourceChunk],
    ) -> list[RokunoheMinuteThemeChunkAnalysis]:
        """
        チャンク一覧へクラスタ番号と候補テーマラベルを付与します。

        先にembeddingだけでK-meansクラスタ番号を決め、その後で各チャンク本文を
        LLMへ渡して候補ラベルを抽出します。クラスタリングと候補ラベル抽出を
        1つのRokunoheMinuteThemeChunkAnalysisへまとめることで、後続のクラスタ命名と
        DB保存が同じVOだけを見れば済むようにします。
        """
        logger.info(
            "Rokunohe theme analysis clustering started: chunks=%s",
            len(chunks),
        )
        cluster_indexes = self._cluster_chunks(chunks)
        logger.info(
            "Rokunohe theme analysis candidate label extraction started: chunks=%s",
            len(chunks),
        )
        analyses = []
        total_count = len(chunks)
        for current_index, (chunk, cluster_index) in enumerate(
            zip(chunks, cluster_indexes),
            start=1,
        ):
            if (
                current_index == 1
                or current_index % 10 == 0
                or current_index == total_count
            ):
                logger.info(
                    "Rokunohe theme analysis extracting candidate labels: %s/%s chunk_id=%s",
                    current_index,
                    total_count,
                    chunk.chroma_id,
                )
            labels = self.label_service.extract_candidate_labels(chunk.document)
            analyses.append(
                RokunoheMinuteThemeChunkAnalysis(
                    source_chunk=chunk,
                    candidate_labels=labels,
                    cluster_index=cluster_index,
                )
            )
        logger.info(
            "Rokunohe theme analysis candidate label extraction completed: chunks=%s",
            len(analyses),
        )
        return analyses

    def _cluster_chunks(
        self,
        chunks: list[RokunoheMinutesThemeSourceChunk],
    ) -> list[int]:
        """
        チャンクembeddingをK-meansでクラスタ番号へ変換します。

        Chroma DBに保存済みのembeddingを使い、本文を再度LLMへ投げずに
        近い議論同士を機械的にまとめます。クラスタ数は対象チャンク数を超えないようにし、
        乱数シードを固定して同じ入力なら同じ初期重心から処理を始めます。
        """
        cluster_count = min(self.default_cluster_count, len(chunks))
        if cluster_count <= 0:
            return []
        if cluster_count == 1:
            return [0]

        logger.info(
            "Rokunohe theme analysis K-means started: chunks=%s cluster_count=%s random_state=%s",
            len(chunks),
            cluster_count,
            self.random_state,
        )
        embeddings = np.array([chunk.embedding for chunk in chunks])
        centroids = self._initialize_centroids(embeddings, cluster_count)
        labels = np.zeros(len(chunks), dtype=int)

        for _ in range(100):
            distances = np.linalg.norm(embeddings[:, np.newaxis] - centroids, axis=2)
            next_labels = distances.argmin(axis=1)
            next_centroids = centroids.copy()
            for cluster_index in range(cluster_count):
                members = embeddings[next_labels == cluster_index]
                if len(members) > 0:
                    next_centroids[cluster_index] = members.mean(axis=0)

            if np.array_equal(labels, next_labels) and np.allclose(
                centroids, next_centroids
            ):
                break

            labels = next_labels
            centroids = next_centroids

        logger.info("Rokunohe theme analysis K-means completed")
        return [int(label) for label in labels]

    def _initialize_centroids(
        self,
        embeddings: np.ndarray,
        cluster_count: int,
    ) -> np.ndarray:
        """
        K-meansの初期重心として使うembeddingを決定的に選びます。

        random_stateで固定した乱数生成器を使うことで、同じ入力チャンク集合なら
        再実行時も同じ初期重心を選び、分析結果の揺れを抑えます。
        """
        rng = np.random.default_rng(self.random_state)
        initial_indexes = rng.choice(len(embeddings), size=cluster_count, replace=False)
        return embeddings[initial_indexes].copy()

    def _create_cluster_analyses(
        self,
        chunk_analyses: list[RokunoheMinuteThemeChunkAnalysis],
    ) -> list[RokunoheMinuteThemeClusterAnalysis]:
        """
        チャンク分析結果をクラスタ単位へ畳み込み、代表テーマ名を付与します。

        _create_chunk_analysesで得たcluster_indexごとにチャンクを束ね、
        各クラスタの代表チャンクIDをembedding重心に最も近いチャンクから選びます。
        その後、クラスタ内の候補ラベルと本文抜粋をLLMへ渡して、人間が読むための
        代表テーマ名を生成します。
        """
        clusters = {}
        for chunk_analysis in chunk_analyses:
            clusters.setdefault(chunk_analysis.cluster_index, []).append(chunk_analysis)

        cluster_analyses = []
        total_clusters = len(clusters)
        logger.info(
            "Rokunohe theme analysis cluster naming started: clusters=%s",
            total_clusters,
        )
        for current_index, (cluster_index, cluster_chunks) in enumerate(
            sorted(clusters.items()),
            start=1,
        ):
            logger.info(
                "Rokunohe theme analysis naming cluster: %s/%s cluster_index=%s chunks=%s",
                current_index,
                total_clusters,
                cluster_index,
                len(cluster_chunks),
            )
            representative_chunk_id = self._find_representative_chunk_id(cluster_chunks)
            label = self.label_service.name_cluster(cluster_chunks)
            cluster_analyses.append(
                RokunoheMinuteThemeClusterAnalysis(
                    cluster_index=cluster_index,
                    label=label,
                    representative_chunk_id=representative_chunk_id,
                    chunks=cluster_chunks,
                )
            )
        logger.info(
            "Rokunohe theme analysis cluster naming completed: clusters=%s",
            len(cluster_analyses),
        )
        return cluster_analyses

    @staticmethod
    def _find_representative_chunk_id(
        chunks: list[RokunoheMinuteThemeChunkAnalysis],
    ) -> str:
        """
        クラスタを代表するチャンクIDを選びます。

        単一チャンクのクラスタならそのチャンクを代表にします。複数チャンクがある場合は
        embedding平均をクラスタ重心とみなし、重心に最も近いチャンクを代表として選びます。
        ビューアではこのIDをクラスタの入口として使います。
        """
        if len(chunks) == 1:
            return chunks[0].source_chunk.chroma_id

        embeddings = np.array([chunk.source_chunk.embedding for chunk in chunks])
        centroid = embeddings.mean(axis=0)
        distances = np.linalg.norm(embeddings - centroid, axis=1)
        nearest_index = int(distances.argmin())
        return chunks[nearest_index].source_chunk.chroma_id
