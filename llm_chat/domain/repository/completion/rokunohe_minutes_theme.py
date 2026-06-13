from django.db import transaction
from django.utils import timezone

from llm_chat.domain.valueobject.completion.rokunohe_minutes import (
    RokunoheMinuteThemeClusterAnalysis,
)
from llm_chat.models import (
    RokunoheMinuteThemeAnalysisJob,
    RokunoheMinuteThemeChunk,
    RokunoheMinuteThemeCluster,
)


class RokunoheMinuteThemeAnalysisRepository:
    """
    六戸町会議録テーマ分析結果のDjango DB永続化を担当するRepository。

    テーマ分析の正本はChroma DBではなくDjango DBに置きます。このRepositoryは、
    Serviceが生成したクラスタ分析VOを、ジョブ、クラスタ、チャンクの3階層モデルへ
    保存するための境界です。

    1. 再実行前に既存ジョブ一式を削除し、画面から見える分析結果を常に最新1世代にする。
    2. 実行開始時にrunningジョブを作り、成功/失敗のどちらでも同じジョブへ結果を集約する。
    3. クラスタごとの集計値と、チャンクごとの候補ラベル・出典情報を同一transactionで保存する。
    4. 完了時は件数と完了日時を更新し、失敗時はエラー内容を残す。
    """

    def reset_analysis_results(self) -> int:
        """
        保存済みテーマ分析結果を全削除し、次の実行結果だけが残る状態にします。

        ジョブを削除すると、外部キーのcascadeによりクラスタとチャンクも削除されます。
        テーマ分析は冪等に再実行する前提のため、過去世代を残さず最新結果だけを
        ビューアや後続処理から参照できるようにします。
        """
        deleted_count, _ = RokunoheMinuteThemeAnalysisJob.objects.all().delete()
        return deleted_count

    def create_job(
        self,
        *,
        requested_cluster_count: int,
        llm_model_name: str,
    ) -> RokunoheMinuteThemeAnalysisJob:
        """
        テーマ分析の開始を表すrunningジョブを作成します。

        Serviceはこのジョブを以降の保存先として使い、成功時はcompleted、
        失敗時はfailedへ更新します。
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

            for cluster_analysis in clusters:
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
                theme_chunks = [
                    RokunoheMinuteThemeChunk(
                        job=job,
                        cluster=cluster,
                        chunk_id=chunk.source_chunk.chroma_id,
                        source=chunk.source_chunk.source,
                        source_date=chunk.source_chunk.source_date,
                        page=chunk.source_chunk.page,
                        chunk_index=chunk.source_chunk.chunk_index,
                        candidate_labels=chunk.candidate_labels,
                        character_count=len(chunk.source_chunk.document),
                    )
                    for chunk in cluster_analysis.chunks
                ]
                RokunoheMinuteThemeChunk.objects.bulk_create(theme_chunks)

    def mark_completed(
        self,
        *,
        job: RokunoheMinuteThemeAnalysisJob,
        chunk_count: int,
        actual_cluster_count: int,
    ) -> RokunoheMinuteThemeAnalysisJob:
        """
        分析ジョブを完了状態へ更新します。

        保存済みクラスタ/チャンクの実績件数をジョブへ持たせることで、画面の
        フラッシュメッセージや一覧表示が子テーブルを再集計せずに概要を表示できます。
        """
        job.status = RokunoheMinuteThemeAnalysisJob.STATUS_COMPLETED
        job.chunk_count = chunk_count
        job.actual_cluster_count = actual_cluster_count
        job.completed_at = timezone.now()
        job.error_message = ""
        job.save(
            update_fields=[
                "status",
                "chunk_count",
                "actual_cluster_count",
                "completed_at",
                "error_message",
            ]
        )
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
