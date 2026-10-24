from soil_analysis.models import LandReviewTemplate


class LandReviewTemplateRepository:
    """定型評価コメントのデータアクセスを担当するRepository。"""

    @staticmethod
    def get_all():
        """選択・管理画面で使う全テンプレートを取得する。"""
        return LandReviewTemplate.objects.all()
