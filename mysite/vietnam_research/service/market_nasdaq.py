from sqlalchemy.engine.base import Connection

from .market_abstract import MarketAbstract
import pandas as pd


class QueryFactory(object):
    """Flyweightパターン"""
    dataframe_store = {}
    sql_store = {
        'nasdaq_index': 'SELECT ...;',
        'radar_chart': 'SELECT ...;'
    }

    def get(self, param: str, con: Connection):
        if not (param in self.dataframe_store):
            self.dataframe_store[param] = pd.read_sql_query(self.sql_store.get(param), con)
        return self.dataframe_store.get(param)


class MarketNasdaq(MarketAbstract):
    """Nasdaqのマーケットを処理します(scraping)"""
    def get_sbi_topics(self) -> str:
        return pd.read_sql_query(
            '''
            SELECT * FROM SBI_TOPICS 
            ''', self._con)

    def watchlist(self) -> pd.DataFrame:
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
                'NASDAQ' AS mkt
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
        pass

    def get_national_stock_timeline(self):
        """シンプルな時系列を作成します"""
        pass

    def get_national_stock_layers(self):
        """annual layer"""
        pass

    def get_uptrends(self):
        """daily: 移動平均チャート"""
        pass

    def industry_stack(self):
        pass

    def calc_fee(self, price_no_fee):
        """上限手数料（税込み）を上回れば上限手数料を返す"""
        fee = price_no_fee * 0.00495
        maximum_fee_including_tax = 22
        return fee if fee <= maximum_fee_including_tax else maximum_fee_including_tax

    def get_radar_chart_count(self):
        """業種別企業数の占有率 e.g. 農林水産業 31count ÷ 全部 750count = 0.041333"""
        pass

    def get_radar_chart_cap(self):
        """業種別時価総額の占有率 e.g. 農林水産業 2479.07cap ÷ 全部 174707.13cap = 0.014190"""
        pass
