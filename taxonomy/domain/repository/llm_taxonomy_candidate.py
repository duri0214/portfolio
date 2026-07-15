from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from taxonomy.models import (
    Breed,
    Classification,
    Family,
    Genus,
    Kingdom,
    LLMTaxonomyCandidate,
    LLMTaxonomyCandidateGenerationJob,
    Phylum,
    Species,
)


class LLMTaxonomyCandidateRepository:
    """
    LLM分類候補の取得、状態更新、確認済みtaxonomyデータ作成を扱うRepository。
    """

    @staticmethod
    def get_for_review(candidate_id: int) -> LLMTaxonomyCandidate:
        """
        レビュー操作対象の候補を取得します。
        """
        return LLMTaxonomyCandidate.objects.select_related(
            "approved_breed",
            "reviewed_by",
        ).get(pk=candidate_id)

    @staticmethod
    def breed_exists(name: str) -> bool:
        """
        品種名が確認済みtaxonomyデータに存在するかを返します。
        """
        return Breed.objects.filter(name=name).exists()

    @staticmethod
    def create_pending(candidate_data: dict) -> LLMTaxonomyCandidate:
        """
        生成済み候補をレビュー待ちとして保存します。
        """
        return LLMTaxonomyCandidate.objects.create(**candidate_data)

    @staticmethod
    def create_pending_bulk(
        candidate_data_list: list[dict],
    ) -> list[LLMTaxonomyCandidate]:
        """
        生成済み候補をレビュー待ちとしてまとめて保存します。
        """
        return [
            LLMTaxonomyCandidate.objects.create(**candidate_data)
            for candidate_data in candidate_data_list
        ]

    @staticmethod
    def create_generation_job(user) -> LLMTaxonomyCandidateGenerationJob:
        """
        LLM分類候補生成ジョブを準備中状態で作成します。
        """
        return LLMTaxonomyCandidateGenerationJob.objects.create(created_by=user)

    @staticmethod
    def get_generation_job(job_id: int) -> LLMTaxonomyCandidateGenerationJob:
        """
        進捗表示またはステップ実行対象の生成ジョブを取得します。
        """
        return LLMTaxonomyCandidateGenerationJob.objects.select_related(
            "processing_by",
        ).get(pk=job_id)

    @staticmethod
    def latest_generation_job() -> LLMTaxonomyCandidateGenerationJob | None:
        """
        画面表示用に直近の生成ジョブを返します。
        """
        return LLMTaxonomyCandidateGenerationJob.objects.order_by("-created_at").first()

    @staticmethod
    def update_generation_job(
        job: LLMTaxonomyCandidateGenerationJob,
        fields: list[str],
    ) -> None:
        """
        生成ジョブの指定フィールドだけを保存します。
        """
        job.updated_at = timezone.now()
        update_fields = [*fields, "updated_at"]
        LLMTaxonomyCandidateGenerationJob.objects.bulk_update([job], update_fields)

    @staticmethod
    def acquire_generation_job_processing(
        job_id: int,
        user,
        processing_token: str,
    ) -> LLMTaxonomyCandidateGenerationJob | None:
        """
        未処理中の生成ジョブだけを処理中に更新して取得します。
        """
        now = timezone.now()
        stale_processing_started_at = now - timedelta(minutes=5)
        updated_count = (
            LLMTaxonomyCandidateGenerationJob.objects.filter(
                pk=job_id,
                status__in=[
                    LLMTaxonomyCandidateGenerationJob.JobStatus.PENDING,
                    LLMTaxonomyCandidateGenerationJob.JobStatus.RUNNING,
                ],
            )
            .filter(
                Q(is_processing=False)
                | Q(processing_started_at__lt=stale_processing_started_at)
            )
            .update(
                is_processing=True,
                processing_started_at=now,
                processing_by=user,
                processing_token=processing_token,
                updated_at=now,
            )
        )
        if updated_count == 0:
            return None
        return LLMTaxonomyCandidateRepository.get_generation_job(job_id)

    @staticmethod
    def release_generation_job_processing(
        job: LLMTaxonomyCandidateGenerationJob,
    ) -> None:
        """
        生成ジョブの1ステップ実行中フラグを解除します。
        """
        job.is_processing = False
        job.processing_started_at = None
        job.processing_by = None
        job.processing_token = ""
        LLMTaxonomyCandidateRepository.update_generation_job(
            job,
            [
                "is_processing",
                "processing_started_at",
                "processing_by",
                "processing_token",
            ],
        )

    @staticmethod
    def pending_candidates() -> list[LLMTaxonomyCandidate]:
        """
        現在レビュー待ちの候補を作成順に返します。
        """
        return list(
            LLMTaxonomyCandidate.objects.filter(
                status=LLMTaxonomyCandidate.ReviewStatus.PENDING,
            ).order_by("created_at", "pk")
        )

    @staticmethod
    def existing_hierarchy_lines(limit: int = 80) -> list[str]:
        """
        LLM生成時に参照する既存taxonomy階層を返します。
        """
        species_list = Species.objects.select_related(
            "genus__family__classification__phylum__kingdom"
        ).order_by(
            "genus__family__classification__phylum__kingdom__name",
            "genus__family__classification__phylum__name",
            "genus__family__classification__name",
            "genus__family__name",
            "genus__name",
            "name",
        )[
            :limit
        ]
        return [
            " > ".join(
                [
                    species.genus.family.classification.phylum.kingdom.name,
                    species.genus.family.classification.phylum.name,
                    species.genus.family.classification.name,
                    species.genus.family.name,
                    species.genus.name,
                    species.name,
                ]
            )
            for species in species_list
        ]

    @staticmethod
    def update_metadata(candidate: LLMTaxonomyCandidate) -> None:
        """
        レビュー用に上書きされた出典とメモを保存します。
        """
        candidate.updated_at = timezone.now()
        LLMTaxonomyCandidate.objects.bulk_update(
            [candidate],
            ["source_name", "source_url", "llm_note", "updated_at"],
        )

    @staticmethod
    @transaction.atomic
    def approve(candidate: LLMTaxonomyCandidate, reviewer) -> Breed:
        """
        候補の分類階層と品種を登録し、候補を承認済みに更新します。

        同名の品種が既に登録済みの場合は既存品種を使い、承認操作を冪等に扱います。
        """
        kingdom = LLMTaxonomyCandidateRepository._get_or_create_root(
            Kingdom,
            candidate.kingdom_name,
            candidate.kingdom_name_en,
        )
        phylum = LLMTaxonomyCandidateRepository._get_or_create_child(
            Phylum,
            candidate.phylum_name,
            candidate.phylum_name_en,
            kingdom=kingdom,
        )
        classification = LLMTaxonomyCandidateRepository._get_or_create_child(
            Classification,
            candidate.classification_name,
            candidate.classification_name_en,
            phylum=phylum,
        )
        family = LLMTaxonomyCandidateRepository._get_or_create_child(
            Family,
            candidate.family_name,
            candidate.family_name_en,
            classification=classification,
        )
        genus = LLMTaxonomyCandidateRepository._get_or_create_child(
            Genus,
            candidate.genus_name,
            candidate.genus_name_en,
            family=family,
        )
        species = LLMTaxonomyCandidateRepository._get_or_create_child(
            Species,
            candidate.species_name,
            candidate.species_name_en,
            genus=genus,
        )
        breed, _ = Breed.objects.get_or_create(
            name=candidate.breed_name,
            defaults={
                "name_kana": candidate.breed_name_kana,
                "image": "",
                "remark": candidate.llm_note or None,
                "species": species,
            },
        )

        reviewed_at = timezone.now()
        candidate.status = LLMTaxonomyCandidate.ReviewStatus.APPROVED
        candidate.approved_breed = breed
        candidate.reviewed_by = reviewer
        candidate.reviewed_at = reviewed_at
        candidate.updated_at = reviewed_at
        LLMTaxonomyCandidate.objects.bulk_update(
            [candidate],
            ["status", "approved_breed", "reviewed_by", "reviewed_at", "updated_at"],
        )
        return breed

    @staticmethod
    def reject(candidate: LLMTaxonomyCandidate, reviewer) -> None:
        """
        候補を却下済みに更新します。
        """
        reviewed_at = timezone.now()
        candidate.status = LLMTaxonomyCandidate.ReviewStatus.REJECTED
        candidate.reviewed_by = reviewer
        candidate.reviewed_at = reviewed_at
        candidate.updated_at = reviewed_at
        LLMTaxonomyCandidate.objects.bulk_update(
            [candidate],
            ["status", "reviewed_by", "reviewed_at", "updated_at"],
        )

    @staticmethod
    def _get_or_create_root(model, name: str, name_en: str):
        instance, _ = model.objects.get_or_create(
            name=name,
            defaults={"name_en": name_en or name},
        )
        return instance

    @staticmethod
    def _get_or_create_child(model, name: str, name_en: str, **parent):
        instance, _ = model.objects.get_or_create(
            name=name,
            **parent,
            defaults={"name_en": name_en or name},
        )
        return instance
