from soil_analysis.models import Company


class CompanyRepository:
    @staticmethod
    def get_by_category(category_id: int) -> list[Company]:
        """
        カテゴリIDを指定して会社リストを取得します

        Args:
            category_id: カテゴリID

        Returns:
            list[Company]: 会社のリスト
        """
        return list(Company.objects.filter(category_id=category_id).order_by("name"))
