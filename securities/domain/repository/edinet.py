from securities.models import Company


class EdinetRepository:
    @staticmethod
    def get_industry_name(edinet_code: str) -> str | None:
        try:
            company = Company.objects.get(edinet_code=edinet_code)
            return company.submitter_industry
        except Company.DoesNotExist:
            return None
