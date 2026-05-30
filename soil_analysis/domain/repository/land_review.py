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
