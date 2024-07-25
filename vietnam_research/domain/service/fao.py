import pandas as pd
from django.db.models import QuerySet

from vietnam_research.models import FaoFoodBalanceRankers


class FaoRetrievalService:
    @staticmethod
    def get_ranked_items(item: str, element: str, rank_limit: int) -> QuerySet:
        return FaoFoodBalanceRankers.objects.filter(
            item=item,
            element=element,
            rank__lte=rank_limit,
        ).values()

    @staticmethod
    def to_pivot(df: pd.DataFrame):
        if not df.empty:
            pivot_df = df.pivot(index="rank", columns="year", values="name")
            return pivot_df.reset_index().to_dict("records")
        else:
            return []

    def to_dict(self, item: str, element: str, rank_limit: int):
        df = pd.DataFrame(list(self.get_ranked_items(item, element, rank_limit)))
        return {"fao_rank_trend": self.to_pivot(df)}
