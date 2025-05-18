from soil_analysis.models import Company


class CompanyRepository:
    @staticmethod
    def get_company_by_id(company_id: int) -> Company:
        return Company.objects.get(pk=company_id)

