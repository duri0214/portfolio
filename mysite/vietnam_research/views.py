"""子供のurls.pyがこの処理を呼び出します"""
import json
from datetime import datetime
from django.shortcuts import render, redirect
from django.contrib.auth import get_user_model
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils.http import urlencode
from django.views.generic import CreateView, ListView, UpdateView
from django.urls import reverse_lazy
from django.http.response import JsonResponse
from django.db.models import Count, Case, When, IntegerField, Sum
from .forms import ArticleForm, WatchlistCreateForm, ExchangeForm, FinancialResultsForm
from .service.market_vietnam import MarketVietnam
from .models import Watchlist, Likes, Articles, FinancialResultWatch, BasicInformation
from django.contrib.auth.decorators import login_required


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

    # articlesとlike
    try:
        loginid = get_user_model().objects.values('id').get(email=request.user)['id']
    except get_user_model().DoesNotExist:
        loginid = None
    articles = Articles.objects.annotate(likes_cnt=Count('likes'))
    articles = articles.select_related('user')
    like_list = Likes.objects.filter(user_id=loginid).values('articles_id')
    articles = articles.annotate(
        is_like=Case(
            When(likes__articles_id__in=like_list, then=1), default=0, output_field=IntegerField()
        )
    ).order_by('-created_at')[:3]

    context = {
        'industry_count': json.dumps(mkt.radar_chart_count()),
        'industry_cap': json.dumps(mkt.radar_chart_cap()),
        'vnindex_timeline': json.dumps(mkt.vnindex_timeline()),
        'vnindex_layers': json.dumps(mkt.vnindex_annual_layers()),
        'articles': articles,
        'basicinfo': BasicInformation.objects.order_by('id').values('item', 'description'),
        'watchlist': mkt.watchlist(),
        'sbi_topics': mkt.sbi_topics(),
        'uptrends': json.dumps(mkt.uptrends()),
        'exchange_form': exchange_form,
        'exchanged': exchanged,
    }

    return render(request, 'vietnam_research/index.html', context)


@login_required
def likes(request, user_id, article_id):
    """いいね！ボタンをクリックしたとき"""
    if request.method == 'POST':
        print(json.loads(request.body), json.loads(request.body).get('status'))
        query = Likes.objects.filter(user=user_id, articles_id=article_id)
        if not query.exists():
            Likes.objects.create(articles_id=article_id, user_id=user_id)
        else:
            query.delete()
        return JsonResponse({"status": "responded by views.py"})


class ArticleCreateView(LoginRequiredMixin, CreateView):
    """いいね！記事作成画面"""
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
        return FinancialResultWatch.objects\
            .values('ticker') \
            .annotate(Count('ticker'), Sum('eps_ok'), Sum('sales_ok'), Sum('guidance_ok')) \
            .order_by('-ticker__count', '-eps_ok__sum', '-sales_ok__sum', '-guidance_ok__sum')


class FinancialResultsDetailListView(ListView):
    template_name = 'vietnam_research/financial_results/detail.html'
    model = FinancialResultWatch

    def get_queryset(self):
        ticker = self.kwargs['ticker']
        return FinancialResultWatch.objects.filter(ticker=ticker).order_by('date')


class FinancialResultsCreateView(LoginRequiredMixin, CreateView):
    """決算データ登録画面"""
    model = FinancialResultWatch
    template_name = "vietnam_research/financial_results/create.html"
    form_class = FinancialResultsForm
    success_url = reverse_lazy("vnm:financial_results")

    def form_valid(self, form):
        form.instance.user_id = self.request.user.id
        return super().form_valid(form)
