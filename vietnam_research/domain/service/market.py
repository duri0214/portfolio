import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path

from django.db.models import F, FloatField
from django.db.models import QuerySet
from django.db.models.functions import Round

from config.settings import STATIC_ROOT
from vietnam_research.domain.repository.market import MarketRepository
from vietnam_research.domain.valueobject.line_chart import LineChartLayer
from vietnam_research.domain.valueobject.radar_chart import Axis, RadarChartLayer
from vietnam_research.forms import ExchangeForm
from vietnam_research.models import Industry

MIN_FEE = 1200000
FEE_RATE = 0.022


class MarketAbstract(ABC):
    def __init__(self):
        self.repository = MarketRepository()

    @abstractmethod
    def sbi_topics(self, **kwargs):
        pass

    @abstractmethod
    def watchlist(self, **kwargs):
        pass

    @abstractmethod
    def calculate_transaction_fee(self, **kwargs):
        pass


class NasdaqMarketDataProvider(MarketAbstract):
    def sbi_topics(self) -> str:
        pass

    def watchlist(self) -> QuerySet:
        pass

    @staticmethod
    def calculate_transaction_fee(price_without_fees: float) -> float:
        pass


class VietnamMarketDataProvider(MarketAbstract):
    def sbi_topics(self, filename: str = "market_report_fo_em_topic.txt"):
        """
        バッチ（daily_sbi_topics.py download_pdf）で取り込んで決まった場所においたtxtを読み込んで返す\n
        バッチは viet/static/viet/sbi_topics に出力して、ここでの読み出しは static/viet/sbi_topics から読むので注意

        Returns:
            str: 新興国ウィークリーレポート

        See Also: https://search.sbisec.co.jp/v2/popwin/info/stock/market_report_fo_em_topic.pdf
        """
        filepath = STATIC_ROOT / Path("vietnam_research/sbi_topics", filename)
        try:
            with open(filepath, encoding="utf8") as f:
                sbi_topics = f.read()
        except FileNotFoundError:
            sbi_topics = None

        return sbi_topics

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

    def radar_chart_count(self) -> list[RadarChartLayer]:
        """
        企業数の業種別占有率 e.g. 農林水産業 31count ÷ 全部 750count = 0.041333\n
        時期の異なる3つのレーダーチャートを重ねて表示します（前月、4ヶ月前、7ヶ月前）\n

        See Also: https://qiita.com/YoshitakaOkada/items/c42483625d6d1622fbc7
        """
        return self.radar_chart(
            rec_type="企業数",
            months_dating_back=[-1, -4, -7],
            aggregate_field="id",
            aggregate_alias="count",
            denominator_field="id",
        )

    def radar_chart_cap(self) -> list[RadarChartLayer]:
        """
        時価総額の業種別占有率 e.g. 農林水産業 2479.07cap ÷ 全部 174707.13cap = 0.014190\n
        時期の異なる3つのレーダーチャートを重ねて表示します（前月、4ヶ月前、7ヶ月前）\n

        See Also: https://qiita.com/YoshitakaOkada/items/c42483625d6d1622fbc7
        """
        return self.radar_chart(
            rec_type="時価総額",
            months_dating_back=[-1, -4, -7],
            aggregate_field="marketcap",
            aggregate_alias="marketcap_sum",
            denominator_field="marketcap",
        )

    def uptrend(self) -> dict:
        uptrend = self.repository.get_annotated_uptrend()

        result = {}
        ind_names = self.repository.get_industry_names()
        for ind_name in ind_names:
            result[ind_name] = [x for x in uptrend if x["ind_name"] == ind_name]

        return result


class MarketRetrievalService:
    def __init__(self, request):
        self.request = request
        self.market_vietnam = VietnamMarketDataProvider()
        self.repository = MarketRepository()

    def get_exchange_params(self):
        exchange_params = [
            "current_balance",
            "unit_price",
            "quantity",
            "price_no_fee",
            "fee",
            "price_in_fee",
            "deduction_price",
        ]
        exchanged = {}
        for param in exchange_params:
            if param in self.request.GET:
                exchanged[param] = self.request.GET.get(param)
        return exchanged

    def to_dict(self):
        exchange_form = ExchangeForm()
        login_user = self.request.user
        login_id = login_user.id if login_user.is_authenticated else None

        return {
            "industry_count": json.dumps(
                [x.to_dict() for x in self.market_vietnam.radar_chart_count()]
            ),
            "industry_cap": json.dumps(
                [x.to_dict() for x in self.market_vietnam.radar_chart_cap()]
            ),
            "vnindex_timeline": json.dumps(self.market_vietnam.vnindex_timeline()),
            "vnindex_layers": json.dumps(self.market_vietnam.vnindex_annual_layers()),
            "articles": self.repository.get_articles(login_id),
            "basic_info": self.repository.get_basic_info(),
            "watchlist": self.market_vietnam.watchlist(),
            "sbi_topics": self.market_vietnam.sbi_topics(),
            "uptrend": json.dumps(self.market_vietnam.uptrend()),
            "exchange_form": exchange_form,
            "exchanged": self.get_exchange_params(),
        }
