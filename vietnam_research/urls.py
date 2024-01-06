from django.urls import path

from vietnam_research.views import ArticleCreateView, index, WatchlistRegister, WatchlistEdit, \
    FinancialResultsListView, FinancialResultsDetailListView, FinancialResultsCreateView, LikesView

app_name = 'vnm'
urlpatterns = [
    path('', index, name='index'),
    path('likes/<int:article_id>/<int:user_id>/', LikesView.as_view(), name='likes'),
    path('article/create/', ArticleCreateView.as_view(), name="article_create"),
    path('watchlist/register/', WatchlistRegister.as_view(), name="watchlist_register"),
    path('watchlist/edit/<int:pk>/', WatchlistEdit.as_view(), name="watchlist_edit"),
    path('financial_results/', FinancialResultsListView.as_view(), name="financial_results"),
    path('financial_results/detail/<str:ticker>/', FinancialResultsDetailListView.as_view(),
         name="financial_results_detail"),
    path('financial_results/create/', FinancialResultsCreateView.as_view(), name="financial_results_create")
]
