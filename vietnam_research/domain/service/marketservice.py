import json

from django.db.models import F

from vietnam_research.forms import ExchangeForm
from vietnam_research.models import Articles, BasicInformation
from vietnam_research.service.market_vietnam import MarketVietnam


class MarketRetrievalService:
    def __init__(self, request):
        self.request = request
        self.mkt = MarketVietnam()

    def get_exchange_params(self):
        exchange_params = [
            "current_balance",
            "unit_price",
            "quantity",
            "price_no_fee",
            "fee",
            "price_in_fee",
            "deduction_price",
        ]
        exchanged = {}
        for param in exchange_params:
            if param in self.request.GET:
                exchanged[param] = self.request.GET.get(param)
        return exchanged

    def to_dict(self):
        exchange_form = ExchangeForm()
        login_user = self.request.user
        login_id = login_user.id if login_user.is_authenticated else None

        return {
            "industry_count": json.dumps(self.mkt.radar_chart_count()),
            "industry_cap": json.dumps(self.mkt.radar_chart_cap()),
            "vnindex_timeline": json.dumps(self.mkt.vnindex_timeline()),
            "vnindex_layers": json.dumps(self.mkt.vnindex_annual_layers()),
            "articles": Articles.with_state(login_id)
            .annotate(user_name=F("user__email"))
            .order_by("-created_at")[:3],
            "basicinfo": BasicInformation.objects.order_by("id").values(
                "item", "description"
            ),
            "watchlist": self.mkt.watchlist(),
            "sbi_topics": self.mkt.sbi_topics(),
            "uptrends": json.dumps(self.mkt.uptrends()),
            "exchange_form": exchange_form,
            "exchanged": self.get_exchange_params(),
        }


class MarketCalculationService:
    def __init__(self, request):
        self.request = request
        self.mkt = MarketVietnam()
        self.data = {}

    def calculate(self, cleaned_data):
        self.data["current_balance"] = cleaned_data["current_balance"]
        self.data["unit_price"] = cleaned_data["unit_price"]
        self.data["quantity"] = cleaned_data["quantity"]
        self.data["price_no_fee"] = self.data["unit_price"] * self.data["quantity"]
        self.data["fee"] = self.mkt.calc_fee(
            price_without_fees=self.data["price_no_fee"]
        )
        self.data["price_in_fee"] = self.data["price_no_fee"] + self.data["fee"]
        self.data["deduction_price"] = (
            self.data["current_balance"] - self.data["price_in_fee"]
        )
