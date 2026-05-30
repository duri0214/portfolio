from django.db.models import QuerySet

from soil_analysis.models import LandBlock


class LandBlockRepository:
    """
    LandBlock関連のデータアクセスを担当するRepository
    """

    @staticmethod
    def get_all() -> QuerySet[LandBlock]:
        """
        全てのブロックを取得します

        Returns:
            QuerySet[LandBlock]: ブロックのクエリセット
        """
        return LandBlock.objects.all()
