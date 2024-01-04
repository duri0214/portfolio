import json
import logging
from datetime import datetime

from django.shortcuts import render, redirect
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.http import urlencode
from django.views.generic import CreateView, ListView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.http.response import HttpResponse
from django.db.models import Count, Sum, F

from register.models import User
from vietnam_research.forms import ArticleForm, WatchlistCreateForm, ExchangeForm, FinancialResultsForm
from vietnam_research.service.market_vietnam import MarketVietnam
from vietnam_research.models import Watchlist, Likes, Articles, FinancialResultWatch, BasicInformation


def index(request):
    """いわばhtmlのページ単位の構成物です"""

    # GETだったら MarketVietnam(), nasdaqが選ばれたらMarketNasdaq()
    mkt = MarketVietnam()

    exchanged = {}
    if request.method == 'POST':
        # ウォッチリスト登録処理
        watchlist_form = WatchlistCreateForm(request.POST)
        if watchlist_form.is_valid():
            watchlist = Watchlist()
            watchlist.symbol = watchlist_form.cleaned_data['buy_symbol']
            watchlist.already_has = True
            watchlist.bought_day = watchlist_form.cleaned_data['buy_date']
            watchlist.stocks_price = watchlist_form.cleaned_data['buy_cost']
            watchlist.stocks_count = watchlist_form.cleaned_data['buy_stocks']
            watchlist.bikou = watchlist_form.cleaned_data['buy_bikou']
            watchlist.save()
            return redirect('vnm:index')

        # 為替計算処理
        exchange_form = ExchangeForm(request.POST)
        if exchange_form.is_valid():
            exchanged['current_balance'] = exchange_form.cleaned_data['current_balance']
            exchanged['unit_price'] = exchange_form.cleaned_data['unit_price']
            exchanged['quantity'] = exchange_form.cleaned_data['quantity']
            exchanged['price_no_fee'] = exchanged['unit_price'] * exchanged['quantity']
            exchanged['fee'] = mkt.calc_fee(price_without_fees=exchanged['price_no_fee'])
            exchanged['price_in_fee'] = exchanged['price_no_fee'] + exchanged['fee']
            exchanged['deduction_price'] = exchanged['current_balance'] - exchanged['price_in_fee']
            response = redirect('vnm:index')
            response['location'] += '?' + urlencode(exchanged)
            return response

    else:
        exchange_form = ExchangeForm()
        params = ['current_balance', 'unit_price', 'quantity', 'price_no_fee', 'fee', 'price_in_fee', 'deduction_price']
        for param in params:
            if param in request.GET:
                exchanged[param] = request.GET.get(param)
        watchlist_form = WatchlistCreateForm()
        watchlist_form.buy_date = datetime.today().strftime("%Y/%m/%d")

    login_user = User.objects.filter(email=request.user).first()
    login_id = None
    if login_user:
        login_id = login_user.id

    # TODO: articlesは試作のため3投稿のみ
    context = {
        'industry_count': json.dumps(mkt.radar_chart_count()),
        'industry_cap': json.dumps(mkt.radar_chart_cap()),
        'vnindex_timeline': json.dumps(mkt.vnindex_timeline()),
        'vnindex_layers': json.dumps(mkt.vnindex_annual_layers()),
        'articles': Articles.with_state(login_id).annotate(user_name=F('user__email')).order_by('-created_at')[:3],
        'basicinfo': BasicInformation.objects.order_by('id').values('item', 'description'),
        'watchlist': mkt.watchlist(),
        'sbi_topics': mkt.sbi_topics(),
        'uptrends': json.dumps(mkt.uptrends()),
        'exchange_form': exchange_form,
        'exchanged': exchanged
    }

    return render(request, 'vietnam_research/index.html', context)


class LikesCreateView(LoginRequiredMixin, CreateView):
    def post(self, request, *args, **kwargs):
        return_value = None
        try:
            Likes.objects.create(user_id=kwargs['user_id'], articles_id=kwargs['article_id'])
            article = Articles.with_state(kwargs['user_id']).get(pk=kwargs['article_id'])
            return_value = json.dumps({'likes_cnt': article.likes_cnt, 'liked_by_me': article.liked_by_me})
        except User.DoesNotExist:
            logging.critical('不正なユーザアカウントからのアクセスがありました')
        except Articles.DoesNotExist:
            logging.critical('不正な記事へのアクセスがありました')

        return HttpResponse(return_value, status=201)


class LikesDeleteView(LoginRequiredMixin, DeleteView):
    def post(self, request, *args, **kwargs):
        return_value = None
        try:
            Likes.objects.filter(user_id=kwargs['user_id'], articles_id=kwargs['article_id']).delete()
            article = Articles.with_state(kwargs['user_id']).get(pk=kwargs['article_id'])
            return_value = json.dumps({'likes_cnt': article.likes_cnt, 'liked_by_me': article.liked_by_me})
        except User.DoesNotExist:
            logging.critical('不正なユーザアカウントからのアクセスがありました')
        except Articles.DoesNotExist:
            logging.critical('不正な記事へのアクセスがありました')

        return HttpResponse(return_value, status=200)


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
        return super().form_valid(form)


class WatchlistEdit(UpdateView):
    """Watchlist編集画面"""
    model = Watchlist
    template_name = "vietnam_research/watchlist/edit.html"
    success_url = reverse_lazy('vnm:index')
    fields = ('symbol', 'bought_day', 'stocks_price', 'stocks_count', 'already_has')

    def get_queryset(self, **kwargs):
        return Watchlist.objects.filter(pk=self.kwargs['pk'])


class FinancialResultsListView(ListView):
    template_name = 'vietnam_research/financial_results/index.html'
    model = FinancialResultWatch

    def get_queryset(self, **kwargs):
        return FinancialResultWatch.objects \
            .values('symbol__code') \
            .annotate(Count('symbol__code'), Sum('eps_ok'), Sum('sales_ok'), Sum('guidance_ok')) \
            .order_by('-symbol__code__count', '-eps_ok__sum', '-sales_ok__sum', '-guidance_ok__sum')


class FinancialResultsDetailListView(ListView):
    template_name = 'vietnam_research/financial_results/detail.html'
    model = FinancialResultWatch

    def get_queryset(self):
        ticker = self.kwargs['ticker']
        return FinancialResultWatch.objects.filter(symbol__code=ticker).order_by('recorded_date')


class FinancialResultsCreateView(LoginRequiredMixin, CreateView):
    """決算データ登録画面"""
    model = FinancialResultWatch
    template_name = "vietnam_research/financial_results/create.html"
    form_class = FinancialResultsForm
    success_url = reverse_lazy("vnm:financial_results")

    def form_valid(self, form):
        form.instance.user_id = self.request.user.id
        return super().form_valid(form)
