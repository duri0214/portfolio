from decimal import Decimal, ROUND_HALF_UP

from dateutil.relativedelta import relativedelta
from django.conf import settings
from django.db.models import Sum
from sqlalchemy.engine.base import Connection

from .market_abstract import MarketAbstract
import pandas as pd

from ..models import Industry, IndClass


class QueryFactory(object):
    """Flyweightパターン"""
    dataframe_store = {}
    sql_store = {
        'vnindex': 'SELECT DISTINCT Y, M, closing_price FROM vietnam_research_vnindex ORDER BY Y, M;',
    }

    def get(self, param: str, con: Connection):
        if not (param in self.dataframe_store):
            self.dataframe_store[param] = pd.read_sql_query(self.sql_store.get(param), con)
        return self.dataframe_store.get(param)


def get_industry_with_ind_class(target_day: list, target_column: str) -> pd.DataFrame:
    """
    いまはたぶん３日分が合計されて１つのグラフになっている
    Args:
        target_day: '2021-10-24'  today: 2021-10-24
        target_column: 'marketcap'
    Returns:
        dataframe
    """
    df_ind_class = pd.DataFrame(list(IndClass.objects.all().values()))
    df_industry = pd.DataFrame(list(Industry.objects.filter(pub_date__in=target_day).values('industry1', target_column)))
    return df_industry.merge(df_ind_class, how='inner', on='industry1').drop('id', axis=1)


def get_end_of_months(month_dating_back: int) -> list:
    """ xヶ月前の月末を取得する
    Args:
        month_dating_back: e.g. -3 today: 2021-10-24
    Returns:
         datetime.date(2021, 7, 30)
    """
    days = []
    df_days = pd.DataFrame(list(Industry.objects.all().order_by('pub_date').values('pub_date')))
    list_days = list(df_days.groupby('pub_date').groups.keys())
    adjusted = list_days[-1] + relativedelta(months=month_dating_back)
    days.append([x for x in list_days if x.strftime("%Y-%m") == adjusted.strftime("%Y-%m")][-1])
    return days


class MarketVietnam(MarketAbstract):
    """ベトナムのマーケットを処理します"""
    def get_sbi_topics(self) -> str:
        filepath = settings.BASE_DIR.joinpath('vietnam_research/static/vietnam_research/sbi_topics/market_report_fo_em_topic.txt')
        if filepath.exists():
            with open(filepath, encoding="utf8") as f:
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

    def get_radar_chart_count(self):
        """業種別企業数の占有率 e.g. 農林水産業 31count ÷ 全部 750count = 0.041333"""
        months_dating_back = [0, -3, -6]
        result = []
        for m in months_dating_back:
            data = get_industry_with_ind_class(get_end_of_months(m), 'marketcap')
            data['ind_name'] = data['industry_class'].astype(str) + '|' + data['industry1']
            each_category = data[['marketcap', 'ind_name']].groupby('ind_name')
            count_of_all = data['marketcap'].count()
            occupancy = each_category['marketcap'].count() / count_of_all
            occupancy = [Decimal(str(x)).quantize(Decimal('0.00') * 100, rounding=ROUND_HALF_UP) for x in occupancy]
            occupancy = [float(x) for x in occupancy]  # DecimalはJSON変換できない
            data = pd.DataFrame({'cnt_per': occupancy}, index=list(each_category.groups.keys()))
            inner = []
            for row in data.iterrows():
                inner.append({"axis": row[0], "value": row[1]["cnt_per"]})
            result.append({"name": '企業数 {0}ヶ月前'.format(m), "axes": inner})
        return result

    def get_radar_chart_cap(self):
        """業種別時価総額の占有率 e.g. 農林水産業 2479.07cap ÷ 全部 174707.13cap = 0.014190"""
        months_dating_back = [0, -3, -6]
        result = []
        for m in months_dating_back:
            data = get_industry_with_ind_class(get_end_of_months(m), 'marketcap')
            data['ind_name'] = data['industry_class'].astype(str) + '|' + data['industry1']
            each_category = data[['marketcap', 'ind_name']].groupby('ind_name')
            sum_of_all = data['marketcap'].sum()
            occupancy = each_category['marketcap'].sum() / sum_of_all
            occupancy = [Decimal(str(x)).quantize(Decimal('0.00') * 100, rounding=ROUND_HALF_UP) for x in occupancy]
            occupancy = [float(x) for x in occupancy]  # DecimalはJSON変換できない
            data = pd.DataFrame({'cap_per': occupancy}, index=list(each_category.groups.keys()))
            inner = []
            for row in data.iterrows():
                inner.append({"axis": row[0], "value": row[1]["cap_per"]})
            result.append({"name": '時価総額 {0}ヶ月前'.format(m), "axes": inner})
        return result
