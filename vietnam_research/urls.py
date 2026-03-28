"""
vietnam_research アプリケーションのURL定義。
各画面（ダッシュボード、ベトナム市場分析、経済指標、ツール、ウォッチリスト、決算データ）へのパスを定義します。
"""

from django.urls import path

from vietnam_research.views import (
    ArticleCreateView,
    IndexView,
    MarketAnalysisView,
    EconomicIndicatorsView,
    StockToolsView,
    WatchlistView,
    WatchlistRegister,
    WatchlistEdit,
    WatchlistDelete,
    FinancialResultsListView,
    FinancialResultsDetailListView,
    FinancialResultsCreateView,
    LikesView,
)

app_name = "vnm"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("market/", MarketAnalysisView.as_view(), name="market"),
    path("economy/", EconomicIndicatorsView.as_view(), name="economy"),
    path("tools/", StockToolsView.as_view(), name="tools"),
    path("watchlist/", WatchlistView.as_view(), name="watchlist"),
    path("likes/<int:article_id>/", LikesView.as_view(), name="likes"),
    path("article/create/", ArticleCreateView.as_view(), name="article_create"),
    path("watchlist/create/", WatchlistRegister.as_view(), name="watchlist_create"),
    path("watchlist/edit/<int:pk>/", WatchlistEdit.as_view(), name="watchlist_edit"),
    path(
        "watchlist/delete/<int:pk>/",
        WatchlistDelete.as_view(),
        name="watchlist_delete",
    ),
    path(
        "financial_results/",
        FinancialResultsListView.as_view(),
        name="financial_results",
    ),
    path(
        "financial_results/detail/<str:ticker>/",
        FinancialResultsDetailListView.as_view(),
        name="financial_results_detail",
    ),
    path(
        "financial_results/create/",
        FinancialResultsCreateView.as_view(),
        name="financial_results_create",
    ),
]
