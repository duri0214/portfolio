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
    六戸町会議録PDFの本文抽出とRAG登録手順を担当するService。

    このServiceは単一PDFファイルを対象に、登録済み確認、PDF本文抽出、
    RAG登録用ドキュメント生成、Repository経由のChroma DB登録までの手順を制御します。
    Chroma DBの具体的な永続化操作はRepositoryへ委譲し、PDF読み取りと登録フローの判断だけを扱います。
    """

    def __init__(self, repository: RokunoheMinutesRagRepository | None = None) -> None:
        """
        六戸町会議録PDFインポートServiceを初期化します。

        Args:
            repository: Chroma DBへの登録済み確認とドキュメント登録を担当するRepository。
                テスト時はモックRepositoryを渡し、本番時は未指定のまま環境変数のAPIキーを使って生成します。
        """
        self.repository = repository or RokunoheMinutesRagRepository(
            api_key=os.getenv("OPENAI_API_KEY") or ""
        )

    def import_pdf(self, pdf_path: Path) -> RokunoheMinutesImportStatus:
        """
        単一PDFを六戸町会議録RAGへ登録します。

        Args:
            pdf_path: ローカルに保存済みの六戸町会議録PDFファイルパス。

        Returns:
            RokunoheMinutesImportStatus:
                - IMPORTED: PDF本文を抽出し、Chroma DBへ登録した。
                - SKIPPED_EXISTING: 同じsource名のPDFが登録済みだった。
                - SKIPPED_EMPTY_TEXT: PDFから登録可能な本文を抽出できなかった。

        Side Effects:
            未登録かつ本文抽出に成功した場合、Repository経由でChroma DBへドキュメントを登録します。
        """
        pdf = RokunoheMinutesPdf(path=pdf_path)
        if self.repository.exists(pdf):
            return RokunoheMinutesImportStatus.SKIPPED_EXISTING

        documents = self._create_documents(pdf)
        if not documents:
            return RokunoheMinutesImportStatus.SKIPPED_EMPTY_TEXT

        self.repository.delete_pdf_documents(pdf)
        self.repository.upsert_documents(documents)
        return RokunoheMinutesImportStatus.IMPORTED

    @staticmethod
    def _create_documents(pdf: RokunoheMinutesPdf) -> list[RokunoheMinutesDocument]:
        """
        PDF本文とメタデータからRAG登録用ドキュメントを作成します。

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
    六戸町会議録RAGの質問応答メッセージ生成を担当するService。

    このServiceは、既にChroma DBへ登録済みの `rokunohe_minutes` collection を前提に、
    ユーザー質問をRepositoryへ渡してRAG回答を取得し、チャット表示用のMessageDTOへ変換します。

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
    六戸町会議録チャンクとクラスタのテーマ名生成を担当するService。

    Attributes:
        model_name: テーマ候補と代表ラベル生成に使用するLLMモデル名。
    """

    model_name = ModelName.GPT_5_MINI

    def __init__(self, *, api_key: str | None = None) -> None:
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY") or "")

    def extract_candidate_labels(self, text: str) -> list[str]:
        """
        単一チャンク本文から候補テーマラベルを抽出します。

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
        クラスタに属するチャンクと候補ラベルから代表テーマ名を生成します。

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
    六戸町会議録RAGの既存チャンクからテーマクラスタリングを生成するService。

    Chroma DBは本文とembeddingの取得元として使い、分析結果の正本はRepository経由で
    Django DBへ保存します。再実行時は保存済み分析結果を削除し、現行collectionに対する
    最新結果だけを残します。

    Attributes:
        default_cluster_count: 通常実行時に生成を試みるクラスタ数。
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
    ) -> None:
        self.rag_repository = rag_repository or RokunoheMinutesRagRepository(
            api_key=os.getenv("OPENAI_API_KEY") or ""
        )
        self.theme_repository = (
            theme_repository or RokunoheMinuteThemeAnalysisRepository()
        )
        self.label_service = label_service or RokunoheMinuteThemeLabelService()

    def run(self):
        """
        Chroma DBの六戸町会議録チャンクからテーマ分析ジョブを作成します。

        Returns:
            RokunoheMinuteThemeAnalysisJob: 完了状態に更新された分析ジョブ。

        Side Effects:
            Chroma DBからチャンクとembeddingを取得し、LLM APIを呼び出して候補ラベルと
            クラスタ代表ラベルを生成し、保存済みテーマ分析結果をリセットしてから
            Django DBへ分析結果を保存します。
        """
        source_date_from = self._get_source_date_from()
        chunks = self.rag_repository.list_theme_source_chunks(
            source_date_from=source_date_from
        )
        if not chunks:
            raise ValueError(
                "rokunohe_minutes collection に直近1年の分析対象がありません。"
            )

        logger.info(
            "Rokunohe theme analysis started: chunks=%s source_date_from=%s",
            len(chunks),
            source_date_from,
        )
        self.theme_repository.reset_analysis_results()
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
        recent_start = timezone.localdate() - timedelta(days=self.default_recent_days)
        return int(recent_start.strftime("%Y%m%d"))

    def _create_chunk_analyses(
        self,
        chunks: list[RokunoheMinutesThemeSourceChunk],
    ) -> list[RokunoheMinuteThemeChunkAnalysis]:
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
        rng = np.random.default_rng(self.random_state)
        initial_indexes = rng.choice(len(embeddings), size=cluster_count, replace=False)
        return embeddings[initial_indexes].copy()

    def _create_cluster_analyses(
        self,
        chunk_analyses: list[RokunoheMinuteThemeChunkAnalysis],
    ) -> list[RokunoheMinuteThemeClusterAnalysis]:
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
        if len(chunks) == 1:
            return chunks[0].source_chunk.chroma_id

        embeddings = np.array([chunk.source_chunk.embedding for chunk in chunks])
        centroid = embeddings.mean(axis=0)
        distances = np.linalg.norm(embeddings - centroid, axis=1)
        nearest_index = int(distances.argmin())
        return chunks[nearest_index].source_chunk.chroma_id
