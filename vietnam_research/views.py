import json
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum
from django.http.response import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView, TemplateView

from vietnam_research.domain.dataprovider.market import VietnamMarketDataProvider
from vietnam_research.domain.repository.like import LikeRepository
from vietnam_research.domain.repository.market import MarketRepository
from vietnam_research.domain.service.exchange import ExchangeService
from vietnam_research.domain.service.fao import FaoRetrievalService
from vietnam_research.domain.service.market import (
    MarketRetrievalService,
)
from vietnam_research.domain.valueobject.exchange import Currency, ExchangeProcess
from vietnam_research.forms import (
    ArticleForm,
    WatchlistCreateForm,
    ExchangeForm,
    FinancialResultsForm,
)
from vietnam_research.models import (
    Watchlist,
    Articles,
    FinancialResultWatch,
)


class IndexView(TemplateView):
    template_name = "vietnam_research/index.html"

    def get_context_data(self, **kwargs):
        # POSTされたフォームの値を取得
        budget = self.request.session.get("budget", 0)
        unit_price = self.request.session.get("unit_price", 0)

        # user情報を取得
        login_user = self.request.user
        login_id = login_user.id if login_user.is_authenticated else None

        # contextを用意
        context = super().get_context_data(**kwargs)
        exchange_service = ExchangeService()
        rate = exchange_service.get_rate(
            base_cur="JPY", dest_cur="VND"
        )  # TODO: 例外処理
        purchasable_units = exchange_service.calc_purchase_units(
            budget=Currency(code="JPY", amount=budget),
            unit_price=Currency(code="VND", amount=unit_price),
        )
        fee = VietnamMarketDataProvider.calculate_transaction_fee(
            price_without_fees=unit_price * purchasable_units
        )
        market_retrieval_service = MarketRetrievalService()
        fao_retrieval_service = FaoRetrievalService()
        context.update(
            {
                "articles": MarketRepository.get_articles(login_id),
                "exchanged": ExchangeProcess(
                    budget_jpy=budget,
                    unit_price=unit_price,
                    rate=rate,
                    purchasable_units=purchasable_units,
                    fee=fee,
                ),
                **market_retrieval_service.to_dict(),
                **fao_retrieval_service.to_dict(
                    item="Fish, Seafood",
                    element="Food supply quantity (kg/capita/yr)",
                    rank_limit=10,
                ),
            }
        )

        return context

    def post(self, request, *args, **kwargs):
        exchange_form = ExchangeForm(request.POST)
        if exchange_form.is_valid():
            request.session["budget"] = exchange_form.cleaned_data["budget"]
            request.session["unit_price"] = exchange_form.cleaned_data["unit_price"]

            return redirect("vnm:index")
        else:
            # フォームが有効でない場合は、フォーム検証エラーを含むページをレンダリング
            return self.render_to_response(
                self.get_context_data(exchange_form=exchange_form)
            )


class LikesView(LoginRequiredMixin, View):
    repository_class = LikeRepository

    def post(self, request, *args, **kwargs):
        try:
            user = self.request.user
            article = self.repository_class.get_article(kwargs["article_id"])
            already_liked = self.repository_class.like_exists(user, article)
            if already_liked:
                self.repository_class.delete_like(user, article)
            else:
                self.repository_class.create_like(user, article)
            already_liked = not already_liked
            article_likes_count = self.repository_class.count_article_likes(article)
            return HttpResponse(
                json.dumps(
                    {"likes_cnt": article_likes_count, "liked_by_me": already_liked}
                ),
                status=200,
            )
        except Articles.DoesNotExist:
            msg = "存在しない記事へのリクエストがありました"
            logging.critical(msg)
        return HttpResponseBadRequest(msg)


class ArticleCreateView(LoginRequiredMixin, CreateView):
    """記事作成画面"""

    model = Articles
    template_name = "vietnam_research/articles/create.html"
    form_class = ArticleForm
    success_url = reverse_lazy("vnm:index")

    def form_valid(self, form):
        form.instance.user_id = self.request.user.id
        return super().form_valid(form)


class WatchlistRegister(CreateView):
    """Watchlist作成画面"""

    model = Watchlist
    template_name = "vietnam_research/watchlist/register.html"
    form_class = WatchlistCreateForm
    success_url = reverse_lazy("vnm:index")

    def form_valid(self, form):
        form.instance.already_has = 1
        form.instance.user_id = self.request.user.id
        return super().form_valid(form)


class WatchlistEdit(UpdateView):
    """Watchlist編集画面"""

    model = Watchlist
    template_name = "vietnam_research/watchlist/edit.html"
    success_url = reverse_lazy("vnm:index")
    fields = ("symbol", "bought_day", "stocks_price", "stocks_count", "already_has")

    def get_queryset(self, **kwargs):
        return Watchlist.objects.filter(pk=self.kwargs["pk"])


class FinancialResultsListView(ListView):
    template_name = "vietnam_research/financial_results/index.html"
    model = FinancialResultWatch

    def get_queryset(self, **kwargs):
        return (
            FinancialResultWatch.objects.values("symbol__code")
            .annotate(
                Count("symbol__code"),
                Sum("eps_ok"),
                Sum("sales_ok"),
                Sum("guidance_ok"),
            )
            .order_by(
                "-symbol__code__count",
                "-eps_ok__sum",
                "-sales_ok__sum",
                "-guidance_ok__sum",
            )
        )


class FinancialResultsDetailListView(ListView):
    template_name = "vietnam_research/financial_results/detail.html"
    model = FinancialResultWatch

    def get_queryset(self):
        ticker = self.kwargs["ticker"]
        return FinancialResultWatch.objects.filter(symbol__code=ticker).order_by(
            "recorded_date"
        )


class FinancialResultsCreateView(LoginRequiredMixin, CreateView):
    """決算データ登録画面"""

    model = FinancialResultWatch
    template_name = "vietnam_research/financial_results/create.html"
    form_class = FinancialResultsForm
    success_url = reverse_lazy("vnm:financial_results")

    def form_valid(self, form):
        form.instance.user_id = self.request.user.id
        return super().form_valid(form)
