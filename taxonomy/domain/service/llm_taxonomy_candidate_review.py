from django.core.exceptions import ObjectDoesNotExist
from django.db import transaction

from taxonomy.domain.repository.llm_taxonomy_candidate import (
    LLMTaxonomyCandidateRepository,
)
from taxonomy.models import Breed, LLMTaxonomyCandidate


class LLMTaxonomyCandidateReviewError(Exception):
    """
    LLM分類候補レビューでユーザーに表示する例外です。
    """


class LLMTaxonomyCandidateReviewService:
    """
    LLM分類候補を確認済みtaxonomyデータへ昇格または却下するServiceです。
    """

    @staticmethod
    def approve(candidate_id: int, reviewer) -> Breed:
        """
        レビュー待ち候補を承認し、確認済み品種として登録します。
        """
        candidate = LLMTaxonomyCandidateReviewService._get_candidate(candidate_id)
        LLMTaxonomyCandidateReviewService._validate_pending(candidate)
        if LLMTaxonomyCandidateRepository.breed_exists(candidate.breed_name):
            raise LLMTaxonomyCandidateReviewError(
                "この名前の品種はすでに登録済みです。"
            )
        return LLMTaxonomyCandidateRepository.approve(candidate, reviewer)

    @staticmethod
    @transaction.atomic
    def approve_many(candidate_ids: list[int], reviewer) -> list[Breed]:
        """
        複数のレビュー待ち候補をまとめて確認済み品種として登録します。
        """
        breeds = []
        for candidate_id in candidate_ids:
            breeds.append(
                LLMTaxonomyCandidateReviewService.approve(candidate_id, reviewer)
            )
        return breeds

    @staticmethod
    def reject(candidate_id: int, reviewer) -> None:
        """
        レビュー待ち候補を確認済みデータへ登録せず却下します。
        """
        candidate = LLMTaxonomyCandidateReviewService._get_candidate(candidate_id)
        LLMTaxonomyCandidateReviewService._validate_pending(candidate)
        LLMTaxonomyCandidateRepository.reject(candidate, reviewer)

    @staticmethod
    def _get_candidate(candidate_id: int) -> LLMTaxonomyCandidate:
        try:
            return LLMTaxonomyCandidateRepository.get_for_review(candidate_id)
        except ObjectDoesNotExist as error:
            raise LLMTaxonomyCandidateReviewError(
                "指定された候補が見つかりません。"
            ) from error

    @staticmethod
    def _validate_pending(candidate: LLMTaxonomyCandidate) -> None:
        if candidate.status == LLMTaxonomyCandidate.ReviewStatus.PENDING:
            return
        raise LLMTaxonomyCandidateReviewError(
            "レビュー待ちではない候補は操作できません。"
        )
