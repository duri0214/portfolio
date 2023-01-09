import logging

from django.db.models import Sum, F, QuerySet, Value, Count, CharField, FloatField
from django.db.models.functions import Concat, Round
from django.conf import settings

from .market_abstract import MarketAbstract
from pathlib import Path
import pandas as pd
from ..models import Industry, Watchlist, VnIndex


class MarketVietnam(MarketAbstract):
    """
    ベトナムのマーケットを処理します
    """
    def get_sbi_topics(self) -> str:
        """
        あらかじめバッチ（daily_sbi_topics.py download_pdf）で取り込んで決まった場所においたtxtを読み込んで返す

        See Also https://search.sbisec.co.jp/v2/popwin/info/stock/market_report_fo_em_topic.pdf

        Returns:
            str: 新興国ウィークリーレポート
        """
        filepath = settings.STATIC_ROOT / Path('vietnam_research/sbi_topics/market_report_fo_em_topic.txt')
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

        return Watchlist.objects\
            .filter(already_has=1)\
            .filter(symbol__industry__recorded_date=Industry.objects.slipped_month_end(0).formatted_recorded_date())\
            .annotate(closing_price=Round(F('symbol__industry__closing_price') * 1000))\
            .annotate(stocks_price_yen=F('stocks_price') / 200)\
            .annotate(buy_price_yen=F('stocks_price_yen') * F('stocks_count'))\
            .annotate(stocks_price_delta=Round((F('closing_price') / F('stocks_price') - 1) * 100, 2))

    @staticmethod
    def vnindex_timeline() -> dict:
        """
        vn-indexのシンプルなYM時系列データセットを作成します

        See Also: https://www.chartjs.org/docs/latest/getting-started/
        """
        records = VnIndex.objects.time_series_closing_price()
        vnindex_timeline = {
            "labels": [record['Y'] + record['M'] for record in records.order_by('Y', 'M')],
            "datasets": [{
                "label": 'VN-Index',
                "data": [float(record['closing_price']) for record in records.order_by('Y', 'M')]
            }]
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
            "labels": [record['M'] for record in records.values('M').distinct().order_by('M')],
            "datasets": []
        }
        for year in [record['Y'] for record in records.values('Y').distinct().order_by('Y')]:
            a_year_records = records.filter(Y=year).order_by('Y', 'M').values('closing_price')
            inner = {"label": year, "data": [float(record['closing_price']) for record in a_year_records]}
            vnindex_layers["datasets"].append(inner)
        # print('\nvnindex_layers: ', vnindex_layers)

        return vnindex_layers

    def get_uptrends(self):
        """daily: 移動平均チャート"""
        uptrends = []
        data = pd.read_sql_query(
            '''
            SELECT DISTINCT
                  u.ind_name
                , CASE
                    WHEN u.market_code = 'HOSE' THEN 'hcm'
                    WHEN u.market_code = 'HNX' THEN 'hn'
                  END mkt
                , u.symbol
                , i.industry1
                , i.company_name
                , u.stocks_price_oldest
                , u.stocks_price_latest
                , u.stocks_price_delta
            FROM vietnam_research_dailyuptrends u INNER JOIN vietnam_research_industry i ON u.symbol = i.symbol
            WHERE i.symbol IN (
                SELECT symbol FROM pythondb.vietnam_research_industry WHERE pub_date = (
                    SELECT max(pub_date) pub_date FROM pythondb.vietnam_research_industry
                )
            )
            ORDER BY u.ind_name, stocks_price_delta DESC;
            ''', self._con)
        for groups in data.groupby('ind_name'):
            # print('\n', groups[0])
            inner = {"ind_name": groups[0], "datasets": []}
            for row in groups[1].iterrows():
                inner["datasets"].append({
                    "mkt": row[1]['mkt'],
                    "symbol": row[1]['symbol'],
                    "industry1": row[1]['industry1'],
                    "company_name": row[1]['company_name'],
                    "stocks_price_oldest": row[1]['stocks_price_oldest'],
                    "stocks_price_latest": row[1]['stocks_price_latest'],
                    "stocks_price_delta": row[1]['stocks_price_delta']
                })
            uptrends.append(inner)
        return uptrends

    def get_industry_stack(self):
        data = Industry.objects\
            .values('pub_date', 'industry1')\
            .annotate(trade_price_of_a_day=Sum('trade_price_of_a_day'))\
            .order_by('pub_date', 'industry1')\
            .values('pub_date', 'industry1', 'trade_price_of_a_day')
        data = pd.DataFrame(list(data))
        data['pub_date'] = data['pub_date'].astype(str).replace('-', '')
        data['trade_price_of_a_day'] = data['trade_price_of_a_day'].astype(float) / 1000000

        industry_pivot = pd.pivot_table(data, index='pub_date',
                                        columns='industry1', values='trade_price_of_a_day', aggfunc='sum')
        industry_stack = {"labels": list(industry_pivot.index), "datasets": []}
        colors = ['#7b9ad0', '#f8e352', '#c8d627', '#d5848b', '#e5ab47']
        colors.extend(['#e1cea3', '#51a1a2', '#b1d7e4', '#66b7ec', '#c08e47', '#ae8dbc'])
        for i, ele in enumerate(data.groupby('industry1').groups.keys()):
            industry_stack["datasets"].append({"label": ele, "backgroundColor": colors[i]})
            value = list(data.groupby('industry1').get_group(ele)['trade_price_of_a_day'])
            industry_stack["datasets"][i]["data"] = value
        # print('\n【data from】\n', industry_pivot)
        # print('\n【data to】\n', industry_stack, '\n')
        return industry_stack

    def calc_fee(self, price_no_fee):
        """最低手数料（税込み）を下回れば最低手数料を返す"""
        fee = price_no_fee * 0.022
        minimum_fee_including_tax = 1320000
        return fee if fee > minimum_fee_including_tax else minimum_fee_including_tax

    @staticmethod
    def radar_chart_count() -> list:
        """
        企業数の業種別占有率 e.g. 農林水産業 31count ÷ 全部 750count = 0.041333\n
        時期の異なる3つのレーダーチャートを重ねて表示します（前月、4ヶ月前、7ヶ月前）\n
        [
            {
                "name": "企業数 0ヶ月前",
                "axes": [{"axis": "1|農林水産業", "value": 0.04}, {"axis": "2|建設業", "value": 0.11}, ... ]
            },
            ...
        ]

        See Also: https://qiita.com/YoshitakaOkada/items/c42483625d6d1622fbc7
        """
        months_dating_back = [-1, -4, -7, -300]
        result = []
        for m in months_dating_back:
            try:
                lastday_of_the_month = Industry.objects.slipped_month_end(m).formatted_recorded_date()
            except Industry.DoesNotExist as e:
                logging.warning(f"market_vietnam.py radar_chart_count() の{m}ヶ月は存在しないため、無視されました")
                continue
            denominator = len(Industry.objects.filter(recorded_date=lastday_of_the_month))
            industry_records = Industry.objects\
                .filter(recorded_date=lastday_of_the_month)\
                .annotate(ind_name=Concat(F('ind_class__industry_class'), Value('|'), F('ind_class__industry1'), output_field=CharField()))\
                .values('ind_name')\
                .annotate(count=Count('id'))\
                .annotate(cnt_per=Round(F('count') / denominator * 100, precision=2, output_field=FloatField()))\
                .order_by('ind_name')
            inner = []
            # print("industry_records(sql): ", industry_records.query)
            for industry_record in industry_records:
                inner.append({
                    "axis": industry_record["ind_name"],
                    "value": industry_record["cnt_per"]
                })
            result.append({
                "name": f"企業数 {m}ヶ月前",
                "axes": inner
            })

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
        months_dating_back = [-1, -4, -7, -300]
        result = []
        for m in months_dating_back:
            try:
                lastday_of_the_month = Industry.objects.slipped_month_end(m).formatted_recorded_date()
            except Industry.DoesNotExist as e:
                logging.warning(f"market_vietnam.py radar_chart_count() の{m}ヶ月は存在しないため、無視されました")
                continue
            denominator = sum([float(x["marketcap"]) for x in Industry.objects.filter(recorded_date=lastday_of_the_month).values('marketcap')])
            industry_records = Industry.objects\
                .filter(recorded_date=lastday_of_the_month)\
                .annotate(ind_name=Concat(F('ind_class__industry_class'), Value('|'), F('ind_class__industry1'), output_field=CharField()))\
                .values('ind_name')\
                .annotate(marketcap_sum=Sum('marketcap'))\
                .annotate(cap_per=Round(F('marketcap_sum') / denominator * 100, precision=2, output_field=FloatField()))\
                .order_by('ind_name')
            # print("industry_records(sql): ", industry_records.query)
            inner = []
            for industry_record in industry_records:
                inner.append({
                    "axis": industry_record["ind_name"],
                    "value": industry_record["cap_per"]
                })
            result.append({
                "name": f"時価総額 {m}ヶ月前",
                "axes": inner
            })

        return result
