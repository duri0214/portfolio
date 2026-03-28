import json
import logging

from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Count, Sum
from django.http.response import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    ListView,
    UpdateView,
    DeleteView,
    TemplateView,
    RedirectView,
)

from vietnam_research.domain.dataprovider.market import VietnamMarketDataProvider
from vietnam_research.domain.repository.like import LikeRepository
from vietnam_research.domain.service.exchange import ExchangeService
from vietnam_research.domain.service.fao import FaoRetrievalService
from vietnam_research.domain.service.market import (
    MarketRetrievalService,
)
from vietnam_research.domain.valueobject.exchange import Currency, ExchangeProcess
from vietnam_research.forms import (
    ArticleForm,
    WatchlistForm,
    ExchangeForm,
    FinancialResultsForm,
    CustomAuthenticationForm,
)
from vietnam_research.models import (
    Watchlist,
    Articles,
    FinancialResultWatch,
)


class CustomLoginView(LoginView):
    """
    カスタムログインビュー。
    CustomAuthenticationFormを使用して、Bootstrap 5のスタイリングを適用したログインフォームを提供します。
    """

    authentication_form = CustomAuthenticationForm


class CustomLogoutView(RedirectView):
    """
    カスタムログアウトビュー。
    ログアウト処理を実行し、トップページへリダイレクトします。
    """

    url = reverse_lazy("index")

    def get(self, request, *args, **kwargs):
        """ログアウト処理を実行"""
        logout(request)
        return super().get(request, *args, **kwargs)


class IndexView(TemplateView):
    """
    ダッシュボード（ホーム）画面を表示するビュー。
    ユーザー投稿（Articles）、ベトナム基本情報、最新ニュース（RSS）などの情報を集約して表示します。
    """

    template_name = "vietnam_research/index.html"

    def get_context_data(self, **kwargs):
        """ダッシュボードに必要なデータをコンテキストに追加します。"""
        # user情報を取得
        login_user = self.request.user
        login_id = login_user.id if login_user.is_authenticated else None

        # contextを用意
        context = super().get_context_data(**kwargs)
        market_retrieval_service = MarketRetrievalService()
        dashboard_data = market_retrieval_service.dashboard_data(login_id)

        context.update(dashboard_data)
        return context


class MarketAnalysisView(TemplateView):
    """
    ベトナム市場分析画面を表示するビュー。
    業種別分析（レーダーチャート）、VN-INDEXの推移、季節要因グラフ、トレンド銘柄などの市場データを提供します。
    """

    template_name = "vietnam_research/market/index.html"

    def get_context_data(self, **kwargs):
        """ベトナム市場分析に必要なデータをコンテキストに追加します。"""
        context = super().get_context_data(**kwargs)
        market_retrieval_service = MarketRetrievalService()
        market_data = market_retrieval_service.market_analysis_data()

        context.update(market_data)
        return context


class EconomicIndicatorsView(TemplateView):
    """
    経済指標画面を表示するビュー。
    鉱工業生産指数(IIP)、消費者物価指数(CPI)の推移、およびFAO統計（水産物供給量）を表示します。
    """

    template_name = "vietnam_research/economy/index.html"

    def get_context_data(self, **kwargs):
        """経済指標およびFAO統計データをコンテキストに追加します。"""
        context = super().get_context_data(**kwargs)
        market_retrieval_service = MarketRetrievalService()
        fao_retrieval_service = FaoRetrievalService()
        economy_data = market_retrieval_service.economic_indicators_data()

        context.update(
            {
                **economy_data,
                **fao_retrieval_service.to_dict(
                    item="Fish, Seafood",
                    element="Food supply quantity (kg/capita/yr)",
                    rank_limit=10,
                ),
            }
        )
        return context


class StockToolsView(TemplateView):
    """
    株式ツール画面を表示するビュー。
    為替・購入計算シミュレーターを提供します。
    """

    template_name = "vietnam_research/tools/index.html"

    def get_context_data(self, **kwargs):
        """計算ツール用の入力値および結果をコンテキストに追加します。"""
        # POSTされたフォームの値を取得
        budget = self.request.session.get("budget", 0)
        unit_price = self.request.session.get("unit_price", 0)

        context = super().get_context_data(**kwargs)
        exchange_service = ExchangeService()
        try:
            rate = exchange_service.rate(base_cur="JPY", dest_cur="VND")
        except ObjectDoesNotExist:
            logging.warning("為替レート(JPY-VND)が取得できませんでした。")
            rate = None

        purchasable_units = exchange_service.calc_purchase_units(
            budget=Currency(code="JPY", amount=budget),
            unit_price=Currency(code="VND", amount=unit_price),
        )
        fee = VietnamMarketDataProvider.calculate_transaction_fee(
            price_without_fees=unit_price * purchasable_units
        )
        # 最低手数料が適用されたか判定
        from vietnam_research.domain.dataprovider.market import MIN_FEE

        is_min_fee = fee == MIN_FEE

        context.update(
            {
                "exchanged": ExchangeProcess(
                    budget_jpy=budget,
                    unit_price=unit_price,
                    rate=rate,
                    purchasable_units=purchasable_units,
                    fee=fee,
                    is_min_fee=is_min_fee,
                ),
                "exchange_form": ExchangeForm(
                    initial={"budget": budget, "unit_price": unit_price}
                ),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        """計算ツールの入力を受け取り、セッションに保存してリダイレクトします。"""
        exchange_form = ExchangeForm(request.POST)
        if exchange_form.is_valid():
            request.session["budget"] = exchange_form.cleaned_data["budget"]
            request.session["unit_price"] = exchange_form.cleaned_data["unit_price"]

            return redirect("vnm:tools")
        else:
            return self.render_to_response(
                self.get_context_data(exchange_form=exchange_form)
            )


class WatchlistView(TemplateView):
    """
    ウォッチリスト画面を表示するビュー。
    ログインユーザーが登録した銘柄のパフォーマンス管理カードを表示します。
    """

    template_name = "vietnam_research/watchlist/index.html"

    def get_context_data(self, **kwargs):
        """ウォッチリストのデータをコンテキストに追加します。"""
        context = super().get_context_data(**kwargs)
        market_retrieval_service = MarketRetrievalService()
        watchlist_data = market_retrieval_service.watchlist_data()

        context.update(watchlist_data)
        return context


class LikesView(View):
    """
    記事に対する「いいね！」アクションを処理するAPIビュー。
    AJAXリクエストを受け取り、いいねの登録・解除を切り替えます。
    """

    repository_class = LikeRepository

    def post(self, request, *args, **kwargs):
        """「いいね！」のトグル処理を行い、最新のカウントと状態を返します。"""
        if not request.user.is_authenticated:
            return HttpResponse(
                json.dumps({"error": "login_required"}),
                status=401,
                content_type="application/json",
            )
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
    """
    ユーザー投稿（記事）作成ビュー。
    ログインユーザーのみが新しい分析記事を投稿できます。
    """

    model = Articles
    template_name = "vietnam_research/articles/create.html"
    form_class = ArticleForm
    success_url = reverse_lazy("vnm:index")

    def form_valid(self, form):
        """投稿ユーザーIDをセットして保存します。"""
        form.instance.user_id = self.request.user.id
        return super().form_valid(form)


class WatchlistRegister(CreateView):
    """
    ウォッチリスト銘柄登録ビュー。
    ログインユーザーが追跡したい銘柄と購入情報を登録します。
    """

    model = Watchlist
    template_name = "vietnam_research/watchlist/create.html"
    form_class = WatchlistForm
    success_url = reverse_lazy("vnm:watchlist")

    def get_form_kwargs(self):
        """フォームにログインユーザー情報を渡します。"""
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.request.user
        return kwargs

    def form_valid(self, form):
        """登録ユーザーIDとデフォルトフラグをセットして保存します。"""
        form.instance.already_has = 1
        form.instance.user_id = self.request.user.id
        return super().form_valid(form)


class WatchlistEdit(UpdateView):
    """
    ウォッチリスト銘柄編集ビュー。
    登録済みの銘柄情報（購入日、価格、数量など）を更新します。
    """

    model = Watchlist
    template_name = "vietnam_research/watchlist/edit.html"
    form_class = WatchlistForm
    success_url = reverse_lazy("vnm:watchlist")

    def get_queryset(self, **kwargs):
        """対象のウォッチリスト項目を取得します。"""
        return Watchlist.objects.filter(pk=self.kwargs["pk"])


class WatchlistDelete(DeleteView):
    """
    ウォッチリスト銘柄削除ビュー。
    登録済みの銘柄をウォッチリストから削除します。
    """

    model = Watchlist
    template_name = "vietnam_research/watchlist/delete_confirm.html"
    success_url = reverse_lazy("vnm:watchlist")

    def get_queryset(self, **kwargs):
        """対象のウォッチリスト項目を取得します。"""
        return Watchlist.objects.filter(pk=self.kwargs["pk"], user=self.request.user)


class FinancialResultsListView(ListView):
    """
    決算データ一覧ビュー。
    主要企業（NASDAQなどの米国株）の銘柄ごとの決算クリア状況をサマリー表示します。
    ※本機能は usa_research アプリ作成前の暫定的な配置です。
    """

    template_name = "vietnam_research/financial_results/index.html"
    model = FinancialResultWatch

    def get_queryset(self, **kwargs):
        """銘柄コードごとに集計された決算データを取得します。"""
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
    """
    決算データ詳細ビュー。
    特定の主要企業（米国株など）に関する時系列の決算発表結果を表示します。
    """

    template_name = "vietnam_research/financial_results/detail.html"
    model = FinancialResultWatch

    def get_queryset(self):
        """指定されたティッカー銘柄の決算履歴を取得します。"""
        ticker = self.kwargs["ticker"]
        return FinancialResultWatch.objects.filter(symbol__code=ticker).order_by(
            "recorded_date"
        )


class FinancialResultsCreateView(LoginRequiredMixin, CreateView):
    """
    決算データ登録ビュー。
    ログインユーザーが特定の銘柄の決算発表結果（EPS, 売上, ガイダンスの成否など）を登録します。
    """

    model = FinancialResultWatch
    template_name = "vietnam_research/financial_results/create.html"
    form_class = FinancialResultsForm
    success_url = reverse_lazy("vnm:financial_results")

    def form_valid(self, form):
        """登録ユーザーIDをセットして保存します。"""
        form.instance.user_id = self.request.user.id
        return super().form_valid(form)
