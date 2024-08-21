import json

import feedparser
import requests

from vietnam_research.domain.dataprovider.market import VietnamMarketDataProvider
from vietnam_research.domain.repository.market import MarketRepository
from vietnam_research.forms import ExchangeForm


class MarketRetrievalService:
    def __init__(self):
        self.repository = MarketRepository()

    @staticmethod
    def get_rss_feed() -> feedparser.util.FeedParserDict:
        url = "https://www.viet-kabu.com/rss/latest.rdf"
        response = requests.get(url)
        response.raise_for_status()
        return feedparser.parse(response.content)

    def to_dict(self):
        exchange_form = ExchangeForm()
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
            "basic_info": self.repository.get_basic_info(),
            "watchlist": vietnam_market_data_provider.watchlist(),
            "uptrend": json.dumps(vietnam_market_data_provider.uptrend()),
            "exchange_form": exchange_form,
            "rss": vietnam_market_data_provider.rss(self.get_rss_feed()),
        }
