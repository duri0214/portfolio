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

    @staticmethod
    def get_company_by_id(company_id: int) -> Company:
        """
        IDを指定して会社を取得します

        Args:
            company_id: 会社ID

        Returns:
            Company: 会社
        """
        return Company.objects.get(pk=company_id)
