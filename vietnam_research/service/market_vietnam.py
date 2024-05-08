import logging
from abc import ABCMeta, abstractmethod
from pathlib import Path

from django.db.models import QuerySet
from django.db.models import Sum, F, Value, Count, CharField, FloatField, Max
from django.db.models.functions import Concat, Round

from config.settings import STATIC_ROOT
from vietnam_research.models import Industry, Watchlist, VnIndex, Uptrends


class MarketAbstract(metaclass=ABCMeta):
    """各マーケットのための基底クラス"""

    @abstractmethod
    def watchlist(self) -> QuerySet:
        raise NotImplementedError()

    @abstractmethod
    def sbi_topics(self) -> str:
        raise NotImplementedError()

    @staticmethod
    @abstractmethod
    def calc_fee(price_without_fees: float) -> float:
        raise NotImplementedError()


class MarketNasdaq(MarketAbstract):
    def watchlist(self) -> QuerySet:
        pass

    def sbi_topics(self) -> str:
        pass

    @staticmethod
    def calc_fee(price_without_fees: float) -> float:
        pass


class MarketVietnam(MarketAbstract):
    """
    ベトナムのマーケットを処理します
    """

    def sbi_topics(self) -> str:
        """
        あらかじめバッチ（daily_sbi_topics.py download_pdf）で取り込んで決まった場所においたtxtを読み込んで返す\n
        バッチは viet/static/viet/sbi_topics に出力して、ここでの読み出しは static/viet/sbi_topics から読むので注意

        Returns:
            str: 新興国ウィークリーレポート

        See Also: https://search.sbisec.co.jp/v2/popwin/info/stock/market_report_fo_em_topic.pdf
        """
        filepath = STATIC_ROOT / Path(
            "vietnam_research/sbi_topics/market_report_fo_em_topic.txt"
        )
        try:
            with open(filepath, encoding="utf8") as f:
                sbi_topics = f.read()
        except FileNotFoundError:
            sbi_topics = None

        return sbi_topics

    def watchlist(self) -> QuerySet:
        """
        ウォッチリストを作成します

        closing_price: 終値は1,000VND単位なので、表示上は1,000を掛けている（1VND単位で表示）\n
        stocks_price_yen: VND→JPNへの変換は 200VND ≒ 1JPY\n
        buy_price_yen: 当初購入額（単価×購入株数）\n
        stocks_price_delta: 直近終値÷当初購入単価

        Returns:
            QuerySet: Watchlistをベースに換算額などの計算を組み合わせたもの
        """
        latest_date = Industry.objects.aggregate(Max("recorded_date"))[
            "recorded_date__max"
        ]

        return (
            Watchlist.objects.filter(already_has=1)
            .filter(symbol__industry__recorded_date=latest_date)
            .annotate(closing_price=Round(F("symbol__industry__closing_price") * 1000))
            .annotate(stocks_price_yen=F("stocks_price") / 200)
            .annotate(buy_price_yen=F("stocks_price_yen") * F("stocks_count"))
            .annotate(
                stocks_price_delta=Round(
                    (F("closing_price") / F("stocks_price") - 1) * 100, 2
                )
            )
        )

    @staticmethod
    def vnindex_timeline() -> dict:
        """
        vn-indexのシンプルなYM時系列データセットを作成します

        See Also: https://www.chartjs.org/docs/latest/getting-started/
        """
        records = VnIndex.objects.time_series_closing_price()
        vnindex_timeline = {
            "labels": [
                record["Y"] + record["M"] for record in records.order_by("Y", "M")
            ],
            "datasets": [
                {
                    "label": "VN-Index",
                    "data": [
                        record["closing_price"] for record in records.order_by("Y", "M")
                    ],
                }
            ],
        }
        # print('\nvnindex_timeline: ', vnindex_timeline)

        return vnindex_timeline

    @staticmethod
    def vnindex_annual_layers() -> dict:
        """
        vn-indexの１２ヶ月ぶんの終値を１つの折れ線にして、年次でグラフに追加していく

        See Also: https://www.chartjs.org/docs/latest/getting-started/
        """
        records = VnIndex.objects.time_series_closing_price()
        vnindex_layers = {
            "labels": [
                record["M"] for record in records.values("M").distinct().order_by("M")
            ],
            "datasets": [],
        }
        for year in [
            record["Y"] for record in records.values("Y").distinct().order_by("Y")
        ]:
            a_year_records = (
                records.filter(Y=year).order_by("Y", "M").values("closing_price")
            )
            inner = {
                "label": year,
                "data": [record["closing_price"] for record in a_year_records],
            }
            vnindex_layers["datasets"].append(inner)
        # print('\nvnindex_layers: ', vnindex_layers)

        return vnindex_layers

    @staticmethod
    def calc_fee(price_without_fees: float) -> float:
        """
        手数料を算出

        Args:
            price_without_fees: 手数料を加味する前の金額

        Returns:
            float: 手数料（約定代金の2.2％）を返す（最低手数料を下回る場合は最低手数料 1,200,000VND）

        See Also: https://www.sbisec.co.jp/ETGate/?_ControlID=WPLETmgR001Control&_DataStoreID=DSWPLETmgR001Control&
        burl=search_foreign&cat1=foreign&cat2=vn&dir=vn%2F&file=foreign_vn_01.html
        """
        fees = price_without_fees * 0.022
        minimum_fees = 1200000

        return fees if fees > minimum_fees else minimum_fees

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
        months_dating_back = [-1, -4, -7]
        result = []
        for m in months_dating_back:
            try:
                end_of_month = Industry.objects.slipped_month_end(
                    m
                ).formatted_recorded_date()
            except Industry.DoesNotExist:
                logging.warning(
                    f"market_vietnam.py radar_chart_count() の{m}ヶ月は存在しないため、無視されました"
                )
                continue
            denominator = len(Industry.objects.filter(recorded_date=end_of_month))
            industry_records = (
                Industry.objects.filter(recorded_date=end_of_month)
                .annotate(
                    ind_name=Concat(
                        F("symbol__ind_class__industry_class"),
                        Value("|"),
                        F("symbol__ind_class__industry1"),
                        output_field=CharField(),
                    )
                )
                .values("ind_name")
                .annotate(count=Count("id"))
                .annotate(
                    cnt_per=Round(
                        F("count") / denominator * 100,
                        precision=2,
                        output_field=FloatField(),
                    )
                )
                .order_by("ind_name")
            )
            inner = []
            # print("industry_records(sql): ", industry_records.query)
            for industry_record in industry_records:
                inner.append(
                    {
                        "axis": industry_record["ind_name"],
                        "value": industry_record["cnt_per"],
                    }
                )
            result.append({"name": f"企業数 {m}ヶ月前", "axes": inner})

        return result

    @staticmethod
    def radar_chart_cap() -> list:
        """
        時価総額の業種別占有率 e.g. 農林水産業 2479.07cap ÷ 全部 174707.13cap = 0.014190\n
        時期の異なる3つのレーダーチャートを重ねて表示します（前月、4ヶ月前、7ヶ月前）\n
        [
            {
                "name": "時価総額 -1ヶ月前",
                "axes": [{"axis": "1|農林水産業", "value": 0}, {"axis": "2|建設業", "value": 0}, ... ]
            },
            ...
        ]

        See Also: https://qiita.com/YoshitakaOkada/items/c42483625d6d1622fbc7
        """
        months_dating_back = [-1, -4, -7]
        result = []
        for m in months_dating_back:
            try:
                end_of_month = Industry.objects.slipped_month_end(
                    m
                ).formatted_recorded_date()
            except Industry.DoesNotExist:
                logging.warning(
                    f"market_vietnam.py radar_chart_count() の{m}ヶ月は存在しないため、無視されました"
                )
                continue
            records = Industry.objects.filter(recorded_date=end_of_month).values(
                "marketcap"
            )
            denominator = sum([record["marketcap"] for record in records])
            industry_records = (
                Industry.objects.filter(recorded_date=end_of_month)
                .annotate(
                    ind_name=Concat(
                        F("symbol__ind_class__industry_class"),
                        Value("|"),
                        F("symbol__ind_class__industry1"),
                        output_field=CharField(),
                    )
                )
                .values("ind_name")
                .annotate(marketcap_sum=Sum("marketcap"))
                .annotate(
                    cap_per=Round(
                        F("marketcap_sum") / denominator * 100,
                        precision=2,
                        output_field=FloatField(),
                    )
                )
                .order_by("ind_name")
            )
            # print("industry_records(sql): ", industry_records.query)
            inner = []
            for industry_record in industry_records:
                inner.append(
                    {
                        "axis": industry_record["ind_name"],
                        "value": industry_record["cap_per"],
                    }
                )
            result.append({"name": f"時価総額 {m}ヶ月前", "axes": inner})

        return result

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
