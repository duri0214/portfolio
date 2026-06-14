import logging

from django.db import connection
from django.db import transaction
from django.utils import timezone

from llm_chat.domain.valueobject.completion.rokunohe_minutes import (
    RokunoheMinuteThemeClusterAnalysis,
    RokunoheMinutesThemeSourceChunk,
)
from llm_chat.models import (
    RokunoheMinuteThemeAnalysisJob,
    RokunoheMinuteThemeChunk,
    RokunoheMinuteThemeCluster,
)

logger = logging.getLogger(__name__)


class RokunoheMinuteThemeAnalysisRepository:
    """
    六戸町会議録テーマ分析結果のDjango DB永続化を担当するRepository。

    テーマ分析の正本はChroma DBではなくDjango DBに置きます。このRepositoryは、
    Serviceが生成したクラスタ分析VOを、ジョブ、クラスタ、チャンクの3階層モデルへ
    保存するための境界です。

    ジョブは「分析ボタン1回分の実行全体」を表します。1,369件のチャンクを処理する
    実行なら、1,369個のジョブではなく1個のジョブが作られ、その配下にクラスタ行と
    チャンク結果行がぶら下がります。DBで保持する状態はジョブ単位の
    running/completed/failedで、`10/1369` のようなチャンク単位の途中経過は
    サーバログに出すだけです。

    1. 完了/失敗済みの既存ジョブ一式を削除し、画面から見える分析結果を常に最新1世代にする。
    2. 既存runningジョブをfailedへ畳み、二重起動の残骸を中断扱いにする。
    3. 実行開始時にrunningジョブを作り、成功/失敗のどちらでも同じジョブへ結果を集約する。
    4. クラスタごとの集計値と、チャンクごとの候補ラベル・出典情報を同一transactionで保存する。
    5. 完了時は件数と完了日時を更新し、失敗時はエラー内容を残す。
    """

    stale_running_message = (
        "新しいテーマ分析実行のため、実行中だったジョブを失敗扱いにしました。"
    )
    expected_chunk_id_collation = "utf8mb4_bin"

    def validate_analysis_preconditions(
        self,
        *,
        chunks: list[RokunoheMinutesThemeSourceChunk],
    ) -> None:
        """
        LLM処理へ進む前に、テーマ分析結果をDB保存できる前提を検証します。

        テーマ分析は長時間かかるため、最後のbulk_createで失敗しそうな条件は
        候補ラベル抽出より前に検出します。完全一致の重複Chroma IDは、DBの
        `job_id + chunk_id` 一意制約で必ず衝突するため即時エラーにします。
        MySQLでは文字列照合順序によって別IDが同一扱いになることがあるため、
        `chunk_id` が厳密照合の `utf8mb4_bin` であることも確認します。
        """
        duplicate_chunk_ids = self._find_duplicate_chunk_ids(chunks)
        if duplicate_chunk_ids:
            preview = ", ".join(duplicate_chunk_ids[:5])
            raise ValueError(
                "テーマ分析対象のChroma IDに重複があります。" f" 重複ID例: {preview}"
            )

        self._validate_chunk_id_collation()

    def _find_duplicate_chunk_ids(
        self,
        chunks: list[RokunoheMinutesThemeSourceChunk],
    ) -> list[str]:
        seen_chunk_ids = set()
        duplicate_chunk_ids = []
        for chunk in chunks:
            if chunk.chroma_id in seen_chunk_ids:
                duplicate_chunk_ids.append(chunk.chroma_id)
                continue
            seen_chunk_ids.add(chunk.chroma_id)
        return duplicate_chunk_ids

    def _validate_chunk_id_collation(self) -> None:
        field = RokunoheMinuteThemeChunk._meta.get_field("chunk_id")
        if field.db_collation != self.expected_chunk_id_collation:
            raise ValueError(
                "テーマ分析結果のchunk_idモデル定義が厳密照合ではありません。"
                f" expected={self.expected_chunk_id_collation} actual={field.db_collation}"
            )

        if connection.vendor != "mysql":
            return

        actual_collation = self._get_chunk_id_db_collation()
        if actual_collation != self.expected_chunk_id_collation:
            raise ValueError(
                "テーマ分析結果のchunk_id DBカラムが厳密照合ではありません。"
                " migrationを適用してください。"
                f" expected={self.expected_chunk_id_collation} actual={actual_collation}"
            )

    def _get_chunk_id_db_collation(self) -> str | None:
        with connection.cursor() as cursor:
            cursor.execute(
                "SHOW FULL COLUMNS FROM llm_chat_rokunohe_minute_theme_chunk LIKE %s",
                ["chunk_id"],
            )
            row = cursor.fetchone()
        return row[2] if row else None

    def mark_running_jobs_failed(self) -> int:
        """
        既存のrunningジョブをfailedへ更新し、新しい分析実行を開始できる状態にします。

        テーマ分析は同期処理ですが、ブラウザの再送信や前回処理の中断でrunningジョブが
        DBへ残ることがあります。superuserだけが起動できる管理操作として割り切り、
        実行開始前に既存runningを中断扱いへ畳みます。
        """
        completed_at = timezone.now()
        return RokunoheMinuteThemeAnalysisJob.objects.filter(
            status=RokunoheMinuteThemeAnalysisJob.STATUS_RUNNING
        ).update(
            status=RokunoheMinuteThemeAnalysisJob.STATUS_FAILED,
            error_message=self.stale_running_message,
            completed_at=completed_at,
        )

    def reset_analysis_results(self) -> int:
        """
        完了/失敗済みテーマ分析結果を削除し、次の実行結果だけが残る状態にします。

        ジョブを削除すると、外部キーのcascadeによりクラスタとチャンクも削除されます。
        テーマ分析は冪等に再実行する前提のため、過去世代を残さず最新結果だけを
        ビューアや後続処理から参照できるようにします。runningジョブはこのメソッドでは
        削除せず、mark_running_jobs_failedで明示的にfailedへ畳みます。
        """
        deleted_count, _ = RokunoheMinuteThemeAnalysisJob.objects.exclude(
            status=RokunoheMinuteThemeAnalysisJob.STATUS_RUNNING
        ).delete()
        return deleted_count

    def create_job(
        self,
        *,
        requested_cluster_count: int,
        llm_model_name: str,
    ) -> RokunoheMinuteThemeAnalysisJob:
        """
        テーマ分析の開始を表すrunningジョブを作成します。

        このジョブは、これから処理する対象チャンク全体をまとめる単位です。
        チャンクごとの進捗レコードは作らず、Serviceはこのジョブをクラスタ/チャンク
        結果の親として使います。成功時はcompleted、失敗時はfailedへ更新します。
        """
        return RokunoheMinuteThemeAnalysisJob.objects.create(
            requested_cluster_count=requested_cluster_count,
            llm_model_name=llm_model_name,
        )

    def save_analysis_result(
        self,
        *,
        job: RokunoheMinuteThemeAnalysisJob,
        clusters: list[RokunoheMinuteThemeClusterAnalysis],
    ) -> None:
        """
        Serviceが生成したクラスタ分析VOをDjango DBのクラスタ/チャンクへ保存します。

        1つの分析ジョブに対して、クラスタ集計行を作り、その配下へチャンク分析行を
        bulk_createします。既存の同一ジョブ配下データを削除してから保存するため、
        リトライやテストで同じジョブへ保存し直しても重複しません。クラスタとチャンクが
        途中で片方だけ残らないよう、処理全体をtransactionで包みます。
        """
        with transaction.atomic():
            RokunoheMinuteThemeChunk.objects.filter(job=job).delete()
            RokunoheMinuteThemeCluster.objects.filter(job=job).delete()
            seen_chunk_ids = set()
            duplicate_count = 0
            total_clusters = len(clusters)

            for current_index, cluster_analysis in enumerate(clusters, start=1):
                logger.info(
                    "Rokunohe theme analysis saving cluster: %s/%s job_id=%s cluster_index=%s chunks=%s",
                    current_index,
                    total_clusters,
                    job.pk,
                    cluster_analysis.cluster_index,
                    cluster_analysis.chunk_count,
                )
                cluster = RokunoheMinuteThemeCluster.objects.create(
                    job=job,
                    cluster_index=cluster_analysis.cluster_index,
                    label=cluster_analysis.label,
                    representative_chunk_id=cluster_analysis.representative_chunk_id,
                    chunk_count=cluster_analysis.chunk_count,
                    character_count=cluster_analysis.character_count,
                    pdf_count=cluster_analysis.pdf_count,
                    source_date_from=cluster_analysis.source_date_from,
                    source_date_to=cluster_analysis.source_date_to,
                )
                theme_chunks = []
                for chunk in cluster_analysis.chunks:
                    chunk_id = chunk.source_chunk.chroma_id
                    if chunk_id in seen_chunk_ids:
                        duplicate_count += 1
                        logger.warning(
                            (
                                "Rokunohe theme analysis duplicate chunk skipped: "
                                "job_id=%s cluster_index=%s chunk_id=%s source=%s page=%s chunk_index=%s"
                            ),
                            job.pk,
                            cluster_analysis.cluster_index,
                            chunk_id,
                            chunk.source_chunk.source,
                            chunk.source_chunk.page,
                            chunk.source_chunk.chunk_index,
                        )
                        continue
                    seen_chunk_ids.add(chunk_id)
                    theme_chunks.append(
                        RokunoheMinuteThemeChunk(
                            job=job,
                            cluster=cluster,
                            chunk_id=chunk_id,
                            source=chunk.source_chunk.source,
                            source_date=chunk.source_chunk.source_date,
                            page=chunk.source_chunk.page,
                            chunk_index=chunk.source_chunk.chunk_index,
                            candidate_labels=chunk.candidate_labels,
                            character_count=len(chunk.source_chunk.document),
                        )
                    )
                RokunoheMinuteThemeChunk.objects.bulk_create(theme_chunks)
            if duplicate_count:
                logger.warning(
                    "Rokunohe theme analysis duplicate chunks skipped: job_id=%s duplicates=%s unique_chunks=%s",
                    job.pk,
                    duplicate_count,
                    len(seen_chunk_ids),
                )

    def mark_completed(
        self,
        *,
        job: RokunoheMinuteThemeAnalysisJob,
        chunk_count: int,
        actual_cluster_count: int,
    ) -> RokunoheMinuteThemeAnalysisJob:
        """
        分析ジョブを完了状態へ更新します。

        完了とは、対象チャンクの束全体に対するクラスタリング、候補ラベル抽出、
        代表ラベル生成、結果保存が終わった状態です。`10/1369` のような
        チャンク単位の進捗をcompletedにする意味ではありません。

        保存済みクラスタ/チャンクの実績件数をジョブへ持たせることで、画面の
        フラッシュメッセージや一覧表示が子テーブルを再集計せずに概要を表示できます。
        すでに別の実行によってfailedへ畳まれたジョブはcompletedへ戻さず、
        runningのまま残っているジョブだけを完了扱いにします。
        """
        RokunoheMinuteThemeAnalysisJob.objects.filter(
            pk=job.pk,
            status=RokunoheMinuteThemeAnalysisJob.STATUS_RUNNING,
        ).update(
            status=RokunoheMinuteThemeAnalysisJob.STATUS_COMPLETED,
            chunk_count=chunk_count,
            actual_cluster_count=actual_cluster_count,
            completed_at=timezone.now(),
            error_message="",
        )
        job.refresh_from_db()
        return job

    def mark_failed(
        self,
        *,
        job: RokunoheMinuteThemeAnalysisJob,
        error_message: str,
    ) -> RokunoheMinuteThemeAnalysisJob:
        """
        分析ジョブを失敗状態へ更新し、呼び出し元へ見せるエラー内容を残します。

        Service側で例外を握りつぶさず再送出するため、このメソッドは永続化された
        失敗状態を残すことだけを担当します。
        """
        job.status = RokunoheMinuteThemeAnalysisJob.STATUS_FAILED
        job.error_message = error_message
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at"])
        return job

    def find_latest_completed_job(self) -> RokunoheMinuteThemeAnalysisJob | None:
        """
        ビューア連携で参照する最新の完了済み分析ジョブを返します。

        失敗中または実行中のジョブは、表示可能な分析結果として扱わないため除外します。
        """
        return (
            RokunoheMinuteThemeAnalysisJob.objects.filter(
                status=RokunoheMinuteThemeAnalysisJob.STATUS_COMPLETED
            )
            .order_by("-created_at")
            .first()
        )

    def find_theme_chunks_by_chunk_ids(
        self,
        *,
        chunk_ids: list[str],
        job: RokunoheMinuteThemeAnalysisJob | None = None,
    ):
        """
        ChromaチャンクIDに対応するテーマ分析チャンクを取得します。

        コレクションビューアから「このChromaチャンクがどのテーマクラスタに属するか」を
        紐づけて表示するための入口です。job未指定時は最新の完了済みジョブを使い、
        完了済みジョブがなければ空のQuerySetを返します。
        """
        target_job = job or self.find_latest_completed_job()
        if target_job is None:
            return RokunoheMinuteThemeChunk.objects.none()

        return RokunoheMinuteThemeChunk.objects.filter(
            job=target_job,
            chunk_id__in=chunk_ids,
        ).select_related("cluster")
