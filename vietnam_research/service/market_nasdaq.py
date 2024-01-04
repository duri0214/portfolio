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
    """
    Nasdaqのマーケットを処理します(scraping)

    See Also: https://site3.sbisec.co.jp/ETGate/?OutSide=on&_ControlID=WPLETmgR001Control&_PageID=WPLETmgR001Mdtl20&_DataStoreID=DSWPLETmgR001Control&_ActionID=DefaultAID&getFlg=on&burl=search_market&cat1=market&cat2=report&dir=report&file=market_report_fo_us_wm.html
    """

    def sbi_topics(self) -> str:
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

    def uptrends(self):
        """daily: 移動平均チャート"""
        pass

    def industry_stack(self):
        pass

    @staticmethod
    def calc_fee(price_without_fees: float) -> float:
        """
        手数料を加味した金額を算出

        Args:
            price_without_fees: 手数料を加味する前の金額

        Returns:
            float: 手数料（約定代金の0.495％）を加味した金額を返す（上限手数料を上回る場合は上限手数料 22USD）

        See Also: https://search.sbisec.co.jp/v2/popwin/attention/trading/stock_gai_23.html
        """
        price_with_fees = price_without_fees * 0.00495
        maximum_fees = 22

        return price_with_fees if price_with_fees <= maximum_fees else maximum_fees
