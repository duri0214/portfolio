import json
import logging
from datetime import datetime, timezone

import feedparser
import requests

from vietnam_research.domain.dataprovider.market import VietnamMarketDataProvider
from vietnam_research.domain.repository.market import MarketRepository
from vietnam_research.domain.valueobject.vietkabu import RssEntryVO
from vietnam_research.forms import ExchangeForm


class MarketRetrievalService:
    """
    マーケット情報取得サービス。
    ダッシュボード、市場分析、経済指標などの各画面で表示するためのデータを集計・加工して提供します。
    """

    def __init__(self):
        self.repository = MarketRepository()

    @staticmethod
    def get_rss_feed() -> dict:
        """
        viet-kabu のRSSをタイムアウト付きで取得し、
        VietnamMarketDataProvider.rss() に渡せる辞書形式で返します。
        取得に失敗した場合は、例外を送出します（タイムアウトなど）。

        Notes:
            - feedparserはFeedParserDictを返すが辞書のように扱える。
            - parsed.get("bozo") は、RSSがXMLとして正しく構成されていない場合にTrueとなります。
        """
        url = "https://www.viet-kabu.com/rss/latest.rdf"
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            parsed = feedparser.parse(response.content)
            if parsed.get("bozo"):
                logging.warning(
                    f"RSSのパース中に不完全なデータが検出されました: {parsed.bozo_exception}"
                )
        except requests.exceptions.RequestException as e:
            logging.error(f"RSS取得時のネットワークエラー: {e}")
            raise
        except Exception as e:
            logging.error(f"RSS取得時の予期せぬエラー: {e}")
            raise

        entries = []
        for entry in parsed.get("entries", []):
            vo = RssEntryVO.from_feedparser_entry(entry)
            entries.append(vo.to_dict())
        feed_updated = parsed.get("feed", {}).get("updated") or parsed.get("updated")
        return {"entries": entries, "feed": {"updated": feed_updated or ""}}

    def get_dashboard_data(self, login_id=None):
        """
        ダッシュボード画面用のデータを取得します。
        ユーザー投稿（Articles）、ベトナム基本情報、および最新ニュース（RSS）を返します。
        """
        vietnam_market_data_provider = VietnamMarketDataProvider()
        try:
            rss_context = vietnam_market_data_provider.rss(self.get_rss_feed())
        except Exception as e:
            logging.warning(f"RSSの取得に失敗しました: {e}")
            rss_context = {"entries": [], "updated": datetime.now(timezone.utc)}

        return {
            "articles": MarketRepository.get_articles(login_id),
            "basic_info": self.repository.get_basic_info(),
            "rss": rss_context,
        }

    @staticmethod
    def get_market_analysis_data():
        """
        市場分析画面用のデータを取得します。
        業種別の企業数・時価総額構成、VN-INDEXの時系列・季節要因データを返します。
        """
        vietnam_market_data_provider = VietnamMarketDataProvider()
        return {
            "industry_count": json.dumps(
                [
                    x.to_dict()
                    for x in vietnam_market_data_provider.radar_chart(
                        rec_type="企業数",
                        months_dating_back=[-1, -4, -7],
                        aggregate_field="id",
                        aggregate_alias="count",
                        denominator_field="id",
                    )
                ]
            ),
            "industry_cap": json.dumps(
                [
                    x.to_dict()
                    for x in vietnam_market_data_provider.radar_chart(
                        rec_type="時価総額",
                        months_dating_back=[-1, -4, -7],
                        aggregate_field="marketcap",
                        aggregate_alias="marketcap_sum",
                        denominator_field="marketcap",
                    )
                ]
            ),
            "vnindex_timeline": json.dumps(
                vietnam_market_data_provider.vnindex_timeline()
            ),
            "vnindex_layers": json.dumps(
                vietnam_market_data_provider.vnindex_annual_layers()
            ),
        }

    @staticmethod
    def get_economic_indicators_data():
        """
        経済指標画面用のデータを取得します。
        IIP（鉱工業生産指数）およびCPI（消費者物価指数）の時系列データを返します。
        """
        vietnam_market_data_provider = VietnamMarketDataProvider()
        return {
            "iip_timeline": json.dumps(vietnam_market_data_provider.iip_timeline()),
            "cpi_timeline": json.dumps(vietnam_market_data_provider.cpi_timeline()),
        }

    @staticmethod
    def get_stock_tools_data():
        """
        株式ツール画面用のデータを取得します。
        上昇トレンド銘柄のリストを返します。
        """
        vietnam_market_data_provider = VietnamMarketDataProvider()
        return {
            "uptrend": json.dumps(vietnam_market_data_provider.uptrend()),
        }

    @staticmethod
    def get_watchlist_data():
        """
        ウォッチリスト画面用のデータを取得します。
        ユーザーが登録した銘柄の最新情報を返します。
        """
        vietnam_market_data_provider = VietnamMarketDataProvider()
        return {
            "watchlist": vietnam_market_data_provider.watchlist(),
        }

    def to_dict(self):
        """
        全てのマーケット情報を網羅した辞書を返します。
        ※レガシーなIndexViewで使用されていた形式を維持しています。
        """
        exchange_form = ExchangeForm()
        vietnam_market_data_provider = VietnamMarketDataProvider()

        # RSSの準備（エラーハンドリング込み）
        try:
            rss_context = vietnam_market_data_provider.rss(self.get_rss_feed())
        except Exception as e:
            logging.warning(f"RSSの取得に失敗しました: {e}")
            rss_context = {"entries": [], "updated": datetime.now(timezone.utc)}

        return {
            "industry_count": json.dumps(
                [
                    x.to_dict()
                    for x in vietnam_market_data_provider.radar_chart(
                        rec_type="企業数",
                        months_dating_back=[-1, -4, -7],
                        aggregate_field="id",
                        aggregate_alias="count",
                        denominator_field="id",
                    )
                ]
            ),
            "industry_cap": json.dumps(
                [
                    x.to_dict()
                    for x in vietnam_market_data_provider.radar_chart(
                        rec_type="時価総額",
                        months_dating_back=[-1, -4, -7],
                        aggregate_field="marketcap",
                        aggregate_alias="marketcap_sum",
                        denominator_field="marketcap",
                    )
                ]
            ),
            "vnindex_timeline": json.dumps(
                vietnam_market_data_provider.vnindex_timeline()
            ),
            "vnindex_layers": json.dumps(
                vietnam_market_data_provider.vnindex_annual_layers()
            ),
            "iip_timeline": json.dumps(vietnam_market_data_provider.iip_timeline()),
            "cpi_timeline": json.dumps(vietnam_market_data_provider.cpi_timeline()),
            "basic_info": self.repository.get_basic_info(),
            "watchlist": vietnam_market_data_provider.watchlist(),
            "uptrend": json.dumps(vietnam_market_data_provider.uptrend()),
            "exchange_form": exchange_form,
            "rss": rss_context,
        }
