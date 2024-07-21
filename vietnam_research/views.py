import json
import logging
from dataclasses import asdict

import pandas as pd
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum
from django.http.response import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.utils.http import urlencode
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView, TemplateView

from vietnam_research.domain.repository.like import LikeRepository
from vietnam_research.domain.service.market import (
    MarketRetrievalService,
)
from vietnam_research.domain.valueobject.exchange import ExchangeProcess
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
    FaoFoodBalanceRankers,
)


class IndexView(TemplateView):
    template_name = "vietnam_research/index.html"

    def get(self, request, *args, **kwargs):
        market_retrieval_service = MarketRetrievalService(request)
        context = market_retrieval_service.to_dict()
        df = pd.DataFrame(
            list(
                FaoFoodBalanceRankers.objects.filter(
                    item="Fish, Seafood",
                    element="Food supply quantity (kg/capita/yr)",
                    rank__lte=10,
                ).values()
            )
        )
        if not df.empty:
            pivot_df = df.pivot(index="rank", columns="year", values="name")
            context["fao_rank_trend"] = pivot_df.reset_index().to_dict("records")
        else:
            context["fao_rank_trend"] = []

        return render(request, self.template_name, context)

    @staticmethod
    def post(request, *args, **kwargs):
        exchange_form = ExchangeForm(request.POST)
        if exchange_form.is_valid():
            exchange_process = ExchangeProcess(
                exchange_form.cleaned_data["current_balance"],
                exchange_form.cleaned_data["unit_price"],
                exchange_form.cleaned_data["quantity"],
            )
            base_location = redirect("vnm:index")["location"]
            query_string = urlencode(asdict(exchange_process))
            response_location = f"{base_location}?{query_string}#exchange"
            return redirect(response_location)


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
