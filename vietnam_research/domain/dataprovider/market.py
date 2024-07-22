import logging
from abc import ABC, abstractmethod

from django.db.models import F, FloatField
from django.db.models import QuerySet
from django.db.models.functions import Round

from vietnam_research.domain.repository.market import MarketRepository
from vietnam_research.domain.valueobject.line_chart import LineChartLayer
from vietnam_research.domain.valueobject.radar_chart import RadarChartLayer, Axis
from vietnam_research.models import Industry

MIN_FEE = 1200000
FEE_RATE = 0.022


class MarketAbstract(ABC):
    def __init__(self):
        self.repository = MarketRepository()

    @abstractmethod
    def watchlist(self, **kwargs):
        pass

    @abstractmethod
    def calculate_transaction_fee(self, **kwargs):
        pass


class NasdaqMarketDataProvider(MarketAbstract):
    def watchlist(self) -> QuerySet:
        pass

    @staticmethod
    def calculate_transaction_fee(price_without_fees: float) -> float:
        pass


class VietnamMarketDataProvider(MarketAbstract):

    def watchlist(self) -> QuerySet:
        """
        ウォッチリストを作成します

        Returns:
            QuerySet: Watchlistをベースに換算額などの計算を組み合わせたもの
        """
        return self.repository.get_watchlist()

    def vnindex_timeline(self) -> dict:
        """
        vn-indexのシンプルなYM時系列データセットを作成します

        Returns:
            dict: VN-Indexのタイムラインデータ
        See Also: https://www.chartjs.org/docs/latest/getting-started/
        """
        records = self.repository.get_vnindex_timeline()
        return {
            "labels": [record["Y"] + record["M"] for record in records],
            "datasets": [
                LineChartLayer(
                    label="VN-Index",
                    data=[record["closing_price"] for record in records],
                ).to_dict()
            ],
        }

    def vnindex_annual_layers(self) -> dict:
        datasets = []
        for year in self.repository.get_distinct_values("Y"):
            records = self.repository.get_vnindex_at_year(year)
            datasets.append(
                LineChartLayer(
                    label=year,
                    data=[record["closing_price"] for record in records],
                ).to_dict()
            )
        return {
            "labels": self.repository.get_distinct_values("M"),
            "datasets": datasets,
        }

    @staticmethod
    def calculate_transaction_fee(price_without_fees: float) -> float:
        """
        手数料を計算します
        Args:
            price_without_fees: 手数料を加味する前の価格
        Returns:
            float: 手数料 (契約価格の 2.2%) を返す。最低手数料を下回った場合は、最低手数料の1,200,000VND

        See Also: https://www.sbisec.co.jp/ETGate/?_ControlID=WPLETmgR001Control&_DataStoreID=DSWPLETmgR001Control&
        burl=search_foreign&cat1=foreign&cat2=vn&dir=vn%2F&file=foreign_vn_01.html
        """
        fees = price_without_fees * FEE_RATE

        return fees if fees > MIN_FEE else MIN_FEE

    def radar_chart(
        self,
        rec_type: str,
        months_dating_back: list,
        aggregate_field: str,
        aggregate_alias: str,
        denominator_field: str,
    ) -> list[RadarChartLayer]:
        layers: list[RadarChartLayer] = []
        for m in months_dating_back:
            try:
                denominator = self.repository.get_denominator_for(m, denominator_field)
                industry_records = self.repository.get_industry_records_for(
                    m, aggregate_field, aggregate_alias
                )
                industry_records = industry_records.annotate(
                    percent=Round(
                        F(aggregate_alias) / denominator * 100,
                        precision=2,
                        output_field=FloatField(),
                    )
                )

                layers.append(
                    RadarChartLayer(
                        name=f"{rec_type} {m}ヶ月前",
                        axes=[
                            Axis(
                                axis=industry_record["ind_name"],
                                value=industry_record["percent"],
                            )
                            for industry_record in industry_records
                        ],
                    )
                )

            except Industry.DoesNotExist:
                logging.warning(
                    f"market_vietnam.py radar_chart() の{m}ヶ月は存在しないため、無視されました"
                )
                continue

        return layers

    def uptrend(self) -> dict:
        uptrend = self.repository.get_annotated_uptrend()

        result = {}
        ind_names = self.repository.get_industry_names()
        for ind_name in ind_names:
            result[ind_name] = [x for x in uptrend if x["ind_name"] == ind_name]

        return result
