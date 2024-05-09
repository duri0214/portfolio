import json
import logging
from abc import ABC, abstractmethod
from pathlib import Path

from django.db.models import F, Value, CharField, FloatField
from django.db.models import QuerySet
from django.db.models.functions import Concat, Round

from config.settings import STATIC_ROOT
from vietnam_research.domain.repository.marketrepository import MarketRepository
from vietnam_research.forms import ExchangeForm
from vietnam_research.models import Industry, Uptrends

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
        """
        return self.repository.get_vnindex_timeline()

    def vnindex_annual_layers(self) -> dict:
        datasets = []
        for year in self.repository.get_distinct_values("Y"):
            datasets.append(
                {
                    "label": year,
                    "data": [
                        record["closing_price"]
                        for record in self.repository.get_year_records(year)
                    ],
                }
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

    @staticmethod
    def radar_chart(
        rec_type: str,
        months_dating_back: list,
        aggregate_field: str,
        aggregate_alias: str,
        denominator_field: str,
    ) -> list:
        result = []
        for m in months_dating_back:
            try:
                denominator = MarketRepository.get_denominator_for(m, denominator_field)
                industry_records = MarketRepository.get_industry_records_for(
                    m, aggregate_field, aggregate_alias
                )
                industry_records = industry_records.annotate(
                    percent=Round(
                        F(aggregate_alias) / denominator * 100,
                        precision=2,
                        output_field=FloatField(),
                    )
                )
                inner = []

                for industry_record in industry_records:
                    inner.append(
                        {
                            "axis": industry_record["ind_name"],
                            "value": industry_record["percent"],
                        }
                    )
                result.append({"name": f"{rec_type} {m}ヶ月前", "axes": inner})

            except Industry.DoesNotExist:
                logging.warning(
                    f"market_vietnam.py radar_chart() の{m}ヶ月は存在しないため、無視されました"
                )
                continue

        return result

    @staticmethod
    def radar_chart_count() -> list:
        """
        企業数の業種別占有率 e.g. 農林水産業 31count ÷ 全部 750count = 0.041333\n
        時期の異なる3つのレーダーチャートを重ねて表示します（前月、4ヶ月前、7ヶ月前）\n
        [
            {
                "name": "企業数 0ヶ月前",
                "axes": [
                    {"axis": "1|農林水産業", "value": 0.04},
                    {"axis": "2|建設業", "value": 0.11},
                    ...
                 ]
            },
            ...
        ]

        See Also: https://qiita.com/YoshitakaOkada/items/c42483625d6d1622fbc7
        """
        return VietnamMarketDataProvider.radar_chart(
            rec_type="企業数",
            months_dating_back=[-1, -4, -7],
            aggregate_field="id",
            aggregate_alias="count",
            denominator_field="id",
        )

    @staticmethod
    def radar_chart_cap() -> list:
        """
        時価総額の業種別占有率 e.g. 農林水産業 2479.07cap ÷ 全部 174707.13cap = 0.014190\n
        時期の異なる3つのレーダーチャートを重ねて表示します（前月、4ヶ月前、7ヶ月前）\n
        [
            {
                "name": "時価総額 -1ヶ月前",
                "axes": [
                    {"axis": "1|農林水産業", "value": 0},
                    {"axis": "2|建設業", "value": 0},
                    ...
                ]
            },
            ...
        ]

        See Also: https://qiita.com/YoshitakaOkada/items/c42483625d6d1622fbc7
        """
        return VietnamMarketDataProvider.radar_chart(
            rec_type="時価総額",
            months_dating_back=[-1, -4, -7],
            aggregate_field="marketcap",
            aggregate_alias="marketcap_sum",
            denominator_field="marketcap",
        )

    @staticmethod
    def uptrends() -> dict:
        uptrends = (
            Uptrends.objects.prefetch_related("symbol", "ind_class")
            .annotate(
                industry1=F("symbol__ind_class__industry1"),
                industry_class=F("symbol__ind_class__industry_class"),
                ind_name=Concat(
                    F("symbol__ind_class__industry_class"),
                    Value("|"),
                    F("symbol__ind_class__industry1"),
                    output_field=CharField(),
                ),
                url_file_name=F("symbol__market__url_file_name"),
                code=F("symbol__code"),
            )
            .order_by(
                "symbol__ind_class__industry_class",
                "symbol__ind_class__industry1",
                "-stocks_price_delta",
            )
            .values(
                "industry1",
                "ind_name",
                "code",
                "url_file_name",
                "stocks_price_latest",
                "stocks_price_delta",
            )
        )

        result = {}
        ind_names = (
            Uptrends.objects.annotate(
                ind_name=Concat(
                    F("symbol__ind_class__industry_class"),
                    Value("|"),
                    F("symbol__ind_class__industry1"),
                    output_field=CharField(),
                )
            )
            .distinct()
            .order_by("ind_name")
            .values("ind_name")
        )

        ind_names = [x["ind_name"] for x in list(ind_names)]
        for ind_name in ind_names:
            result[ind_name] = [x for x in uptrends if x["ind_name"] == ind_name]

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
            "industry_count": json.dumps(self.market_vietnam.radar_chart_count()),
            "industry_cap": json.dumps(self.market_vietnam.radar_chart_cap()),
            "vnindex_timeline": json.dumps(self.market_vietnam.vnindex_timeline()),
            "vnindex_layers": json.dumps(self.market_vietnam.vnindex_annual_layers()),
            "articles": self.repository.get_articles(login_id),
            "basicinfo": self.repository.get_basic_info(),
            "watchlist": self.market_vietnam.watchlist(),
            "sbi_topics": self.market_vietnam.sbi_topics(),
            "uptrends": json.dumps(self.market_vietnam.uptrends()),
            "exchange_form": exchange_form,
            "exchanged": self.get_exchange_params(),
        }


class MarketCalculationService:
    def __init__(self, request):
        self.request = request
        self.market_vietnam = VietnamMarketDataProvider()
        self.data = {}

    def calculate(self, cleaned_data):
        self.data["current_balance"] = cleaned_data["current_balance"]
        self.data["unit_price"] = cleaned_data["unit_price"]
        self.data["quantity"] = cleaned_data["quantity"]
        self.data["price_no_fee"] = self.data["unit_price"] * self.data["quantity"]
        self.data["fee"] = self.market_vietnam.calculate_transaction_fee(
            price_without_fees=self.data["price_no_fee"]
        )
        self.data["price_in_fee"] = self.data["price_no_fee"] + self.data["fee"]
        self.data["deduction_price"] = (
            self.data["current_balance"] - self.data["price_in_fee"]
        )
