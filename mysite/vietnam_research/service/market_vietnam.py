from django.conf import settings
from sqlalchemy.engine.base import Connection

from .market_abstract import MarketAbstract
import pandas as pd


class QueryFactory(object):
    """Flyweightパターン"""
    dataframe_store = {}
    sql_store = {
        'vnindex': 'SELECT DISTINCT Y, M, closing_price FROM vietnam_research_vnindex ORDER BY Y, M;',
        'radar_chart': """
            SELECT
                CONCAT(c.industry_class, '|', i.industry1) AS ind_name,
                i.marketcap
            FROM vietnam_research_industry i INNER JOIN vietnam_research_indclass c ON i.industry1 = c.industry1
            WHERE DATE(pub_date) = (SELECT DATE(MAX(pub_date)) pub_date FROM vietnam_research_industry);
        """
    }

    def get(self, param: str, con: Connection):
        if not (param in self.dataframe_store):
            self.dataframe_store[param] = pd.read_sql_query(self.sql_store.get(param), con)
        return self.dataframe_store.get(param)


class MarketVietnam(MarketAbstract):
    """ベトナムのマーケットを処理します"""

    def get_sbi_topics(self) -> str:
        filepath = settings.BASE_DIR + '/vietnam_research/static/vietnam_research/sbi_topics/market_report_fo_em_topic.txt'
        f = open(filepath, encoding="utf8")
        sbi_topics = f.read()  # ファイル終端まで全て読んだデータを返す
        f.close()
        return sbi_topics

    def get_watchlist(self) -> pd.DataFrame:
        """ウォッチリストを作成します"""
        return pd.read_sql_query(
            '''
            WITH latest AS (
                SELECT
                    i.symbol, i.closing_price * 1000 closing_price
                FROM vietnam_research_industry i
                WHERE i.pub_date = (SELECT MAX(i.pub_date) pub_date FROM vietnam_research_industry i)
            )
            SELECT DISTINCT
                CASE
                    WHEN market_code = 'HOSE' THEN 'hcm'
                    WHEN market_code = 'HNX' THEN 'hn'
                END mkt
                , w.symbol
                , LEFT(CONCAT(i.industry1, ': ', i.company_name), 14) AS company_name
                , CONCAT(YEAR(w.bought_day), '/', MONTH(w.bought_day), '/',
                    DAY(w.bought_day)) AS bought_day
                , FORMAT(w.stocks_price, 0) AS stocks_price
                , FORMAT(w.stocks_price / 100 / 2, 0) AS stocks_price_yen
                , FORMAT((w.stocks_price / 100 / 2) * w.stocks_count, 0) AS buy_price_yen
                , w.stocks_count
                , i.industry1
                , FORMAT(latest.closing_price, 0) AS closing_price
                , ROUND(((latest.closing_price / w.stocks_price) -1) *100, 2) AS stocks_price_delta
            FROM vietnam_research_watchlist w
                INNER JOIN vietnam_research_industry i ON w.symbol = i.symbol
                INNER JOIN latest ON w.symbol = latest.symbol
            WHERE already_has = 1
            ORDER BY bought_day;
            ''', self._con)

    def get_basicinfo(self) -> pd.DataFrame:
        """国の基本情報"""
        return pd.read_sql_query(
            '''
            SELECT
                  b.item
                , b.description
            FROM vietnam_research_basicinformation b
            ORDER BY b.id;
            ''', self._con)

    def get_national_stock_timeline(self):
        """シンプルな時系列を作成します"""
        query = QueryFactory()
        data = query.get('vnindex', self._con)
        vnindex_timeline = {"labels": list(data['Y'] + data['M']), "datasets": []}
        inner = {"label": 'VN-Index', "data": list(data['closing_price'])}
        vnindex_timeline["datasets"].append(inner)
        return vnindex_timeline

    def get_national_stock_layers(self):
        """annual layer"""
        query = QueryFactory()
        data = query.get('vnindex', self._con)
        vnindex_pivot = data.pivot('Y', 'M', 'closing_price').fillna(0)
        vnindex_layers = {"labels": list(vnindex_pivot.columns.values), "datasets": []}
        for i, yyyy in enumerate(vnindex_pivot.iterrows()):
            inner = {"label": yyyy[0], "data": list(yyyy[1])}
            vnindex_layers["datasets"].append(inner)
        # print('vnindex_pivot: ', vnindex_pivot)
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
            FROM vietnam_research_dailyuptrends u INNER JOIN vietnam_research_industry i
                ON u.symbol = i.symbol
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
        data = pd.read_sql_query(
            '''
            SELECT
                  pub_date
                , industry1
                , truncate(trade_price_of_a_day / 1000000, 2) trade_price_of_a_day
            FROM (
                SELECT
                      DATE_FORMAT(pub_date, '%Y%m%d') pub_date
                    , industry1
                    , SUM(trade_price_of_a_day) AS trade_price_of_a_day
                FROM vietnam_research_industry
                GROUP BY pub_date, industry1
            ) Q
            ORDER BY pub_date, industry1;
            ''', self._con)
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

    def get_radar_chart_count(self):
        """業種別企業数の占有率 e.g. 農林水産業 31count ÷ 全部 750count = 0.041333"""
        query = QueryFactory()
        data = query.get('radar_chart', self._con)
        one_of_category = data.groupby('ind_name').count()
        all_of_category = len(data)
        # One を All で割ったあとの marketcap を list で返す（行のラベルは業種名）
        data = pd.DataFrame({
            'cnt_per': (one_of_category / all_of_category)['marketcap'].values.tolist()
        }, index=list(data.groupby('ind_name').groups.keys()))
        data['cnt_per'] = (data['cnt_per'] * 100).round(1)
        inner = []
        for row in data.iterrows():
            inner.append({"axis": row[0], "value": row[1]["cnt_per"]})
        return [{"name": '企業数', "axes": inner}]

    def get_radar_chart_cap(self):
        """業種別時価総額の占有率 e.g. 農林水産業 2479.07cap ÷ 全部 174707.13cap = 0.014190"""
        query = QueryFactory()
        data = query.get('radar_chart', self._con)
        one_of_category = data.groupby('ind_name').sum()
        all_of_category = data['marketcap'].sum()
        # One を All で割ったあとの marketcap を list で返す（行のラベルは業種名）
        data = pd.DataFrame({
            'cap_per': (one_of_category / all_of_category)['marketcap'].values.tolist()
        }, index=list(data.groupby('ind_name').groups.keys()))
        data['cap_per'] = (data['cap_per'] * 100).round(1)
        inner = []
        for row in data.iterrows():
            inner.append({"axis": row[0], "value": row[1]["cap_per"]})
        return [{"name": '時価総額', "axes": inner}]
