import json
import logging

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Count, Sum
from django.http.response import HttpResponse, HttpResponseBadRequest
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.utils.http import urlencode
from django.views import View
from django.views.generic import CreateView, ListView, UpdateView, TemplateView

from vietnam_research.domain.service.marketservice import (
    MarketRetrievalService,
    MarketCalculationService,
)
from vietnam_research.forms import (
    ArticleForm,
    WatchlistCreateForm,
    ExchangeForm,
    FinancialResultsForm,
)
from vietnam_research.models import (
    Watchlist,
    Likes,
    Articles,
    FinancialResultWatch,
)


class IndexView(TemplateView):
    template_name = "vietnam_research/index.html"

    def get(self, request, *args, **kwargs):
        market_retrieval_service = MarketRetrievalService(request)

        return render(request, self.template_name, market_retrieval_service.to_dict())

    def post(self, request, *args, **kwargs):
        market_calculation_service = MarketCalculationService(request)
        exchange_form = ExchangeForm(request.POST)
        if exchange_form.is_valid():
            market_calculation_service.calculate(exchange_form.cleaned_data)
            response = redirect("vnm:index")
            response["location"] += "?" + urlencode(market_calculation_service.data)
            return response
        return render(
            request, self.template_name, {"data": market_calculation_service.data}
        )


class LikesView(LoginRequiredMixin, View):
    def post(self, request, *args, **kwargs):
        try:
            user = self.request.user
            article = Articles.objects.get(pk=kwargs["article_id"], user=user)
            already_liked = Likes.objects.filter(user=user).exists()

            if already_liked:
                Likes.objects.filter(user=user, articles=article).delete()
            else:
                Likes.objects.create(user=user, articles=article)

            already_liked = not already_liked
            article_likes_count = Likes.objects.filter(articles=article).aggregate(
                likes_count=Count("id")
            )["likes_count"]

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
