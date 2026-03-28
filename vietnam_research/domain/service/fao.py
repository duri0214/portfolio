import pandas as pd
from django.db.models import QuerySet

from vietnam_research.models import FaoFoodBalanceRankers


class FaoRetrievalService:
    """
    FAO（国際連合食糧農業機関）統計データ取得サービス。
    国別の食品バランス（水産物供給量など）のランキングデータを取得・加工します。
    """

    @staticmethod
    def ranked_items(item: str, element: str, rank_limit: int) -> QuerySet:
        """
        指定された項目・要素について、一定の順位以内のレコードを取得します。
        """
        return FaoFoodBalanceRankers.objects.filter(
            item=item,
            element=element,
            rank__lte=rank_limit,
        ).values()

    @staticmethod
    def to_pivot(df: pd.DataFrame):
        """
        DataFrameをピボット（行：順位、列：年、値：国名）し、辞書形式に変換します。
        """
        if not df.empty:
            pivot_df = df.pivot(index="rank", columns="year", values="name")
            return pivot_df.reset_index().to_dict("records")
        else:
            return []

    def to_dict(self, item: str, element: str, rank_limit: int):
        """
        指定された条件のFAO統計データを整形した辞書を返します。
        """
        df = pd.DataFrame(list(self.ranked_items(item, element, rank_limit)))
        return {"fao_rank_trend": self.to_pivot(df)}
