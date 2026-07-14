from django.db import transaction
from django.utils import timezone

from taxonomy.models import (
    Breed,
    Classification,
    Family,
    Genus,
    Kingdom,
    LLMTaxonomyCandidate,
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
    @transaction.atomic
    def approve(candidate: LLMTaxonomyCandidate, reviewer) -> Breed:
        """
        候補の分類階層と品種を作成し、候補を承認済みに更新します。
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
        breed = Breed.objects.create(
            name=candidate.breed_name,
            name_kana=candidate.breed_name_kana,
            image="",
            remark=candidate.review_note or None,
            species=species,
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
