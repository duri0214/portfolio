from django.db.models import Q, QuerySet, F

from securities.domain.valueobject.plot import RequestData
from securities.models import Counting


class PlotRepository:
    @staticmethod
    def get_target_data(request_data: RequestData) -> QuerySet:
        return (
            Counting.objects.select_related("company")
            .filter(
                Q(submit_date__gte=request_data.start_date)
                & Q(submit_date__lte=request_data.end_date)
            )
            .annotate(submitter_industry=F("company__submitter_industry"))
        )
