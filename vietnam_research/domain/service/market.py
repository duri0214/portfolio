import json
from datetime import datetime, timezone

import feedparser
import requests

from vietnam_research.domain.dataprovider.market import VietnamMarketDataProvider
from vietnam_research.domain.repository.market import MarketRepository
from vietnam_research.domain.valueobject.vietkabu import RssEntryVO
from vietnam_research.forms import ExchangeForm


class MarketRetrievalService:
    def __init__(self):
        self.repository = MarketRepository()

    @staticmethod
    def get_rss_feed() -> dict:
        """
        viet-kabu のRSSをタイムアウト付きで取得し、
        VietnamMarketDataProvider.rss() に渡せる辞書形式で返します。
        取得に失敗した場合は、例外を送出します（タイムアウトなど）。

        Notes: feedparserはFeedParserDictを返すが辞書のように扱える。
        """
        url = "https://www.viet-kabu.com/rss/latest.rdf"
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        parsed = feedparser.parse(response.content)
        entries = []
        for entry in parsed.get("entries", []):
            vo = RssEntryVO.from_feedparser_entry(entry)
            entries.append(vo.to_dict())
        feed_updated = parsed.get("feed", {}).get("updated") or parsed.get("updated")
        return {"entries": entries, "feed": {"updated": feed_updated or ""}}

    def to_dict(self):
        exchange_form = ExchangeForm()
        vietnam_market_data_provider = VietnamMarketDataProvider()

        # RSSの準備（エラーハンドリング込み）
        try:
            rss_context = vietnam_market_data_provider.rss(self.get_rss_feed())
        except requests.exceptions.Timeout:
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
