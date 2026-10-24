from django.db.models import QuerySet

from soil_analysis.models import LandReview, LandLedger


class LandReviewRepository:
    """
    LandReview関連のデータアクセスを担当するRepository
    """

    @staticmethod
    def get_by_ledger(land_ledger: LandLedger) -> QuerySet[LandReview]:
        """
        帳簿に紐づく評価データを取得します

        Args:
            land_ledger: 帳簿インスタンス

        Returns:
            QuerySet[LandReview]: 評価データのクエリセット
        """
        return LandReview.objects.filter(land_ledger=land_ledger)

    @staticmethod
    def get_one_by_ledger(land_ledger: LandLedger) -> LandReview | None:
        """台帳に保存済みの評価コメントを1件取得する。"""
        return LandReviewRepository.get_by_ledger(land_ledger).first()

    @staticmethod
    def save(
        land_ledger: LandLedger, comment: str, source: str
    ) -> tuple[LandReview, bool]:
        """台帳ごとに評価コメントを新規作成または更新する。"""
        return LandReview.objects.update_or_create(
            land_ledger=land_ledger,
            defaults={"comment": comment, "source": source},
        )
