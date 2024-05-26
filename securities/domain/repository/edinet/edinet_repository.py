from securities.models import Edinet


class EdinetRepository:
    @staticmethod
    def get_industry_name(edinet_code: str) -> str | None:
        try:
            edinet = Edinet.objects.get(edinet_code=edinet_code)
            return edinet.submitter_industry
        except Edinet.DoesNotExist:
            return None
