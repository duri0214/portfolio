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
    """

    def create_job(
        self,
        *,
        requested_cluster_count: int,
        llm_model_name: str,
    ) -> RokunoheMinuteThemeAnalysisJob:
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
        job.status = RokunoheMinuteThemeAnalysisJob.STATUS_FAILED
        job.error_message = error_message
        job.completed_at = timezone.now()
        job.save(update_fields=["status", "error_message", "completed_at"])
        return job

    def find_latest_completed_job(self) -> RokunoheMinuteThemeAnalysisJob | None:
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
        target_job = job or self.find_latest_completed_job()
        if target_job is None:
            return RokunoheMinuteThemeChunk.objects.none()

        return RokunoheMinuteThemeChunk.objects.filter(
            job=target_job,
            chunk_id__in=chunk_ids,
        ).select_related("cluster")
