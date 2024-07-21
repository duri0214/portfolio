import json
from dataclasses import fields

from vietnam_research.domain.repository.market import MarketRepository
from vietnam_research.domain.valueobject.exchange import (
    ExchangeProcess,
    VietnamMarketDataProvider,
)
from vietnam_research.forms import ExchangeForm


class MarketRetrievalService:
    def __init__(self, request):
        self.request = request
        self.repository = MarketRepository()

    def get_exchange_params(self):
        exchange_params = [f.name for f in fields(ExchangeProcess)]
        return {
            param: self.request.GET.get(param)
            for param in exchange_params
            if param in self.request.GET
        }

    def to_dict(self):
        exchange_form = ExchangeForm()
        login_user = self.request.user
        login_id = login_user.id if login_user.is_authenticated else None
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
            "articles": self.repository.get_articles(login_id),
            "basic_info": self.repository.get_basic_info(),
            "watchlist": vietnam_market_data_provider.watchlist(),
            "sbi_topics": vietnam_market_data_provider.sbi_topics(),
            "uptrend": json.dumps(vietnam_market_data_provider.uptrend()),
            "exchange_form": exchange_form,
            "exchanged": self.get_exchange_params(),
        }
