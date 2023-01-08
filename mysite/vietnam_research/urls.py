"""docstring"""
from django.urls import path
from .views import ArticleCreateView, likes, index, WatchListRegister, WatchListEdit, FinancialResultsListView, \
    FinancialResultsDetailListView, FinancialResultsCreateView

app_name = 'vnm'
urlpatterns = [
    path('', index, name='index'),
    path('likes/<int:user_id>/<int:article_id>/', likes, name='likes'),
    path('article/create/', ArticleCreateView.as_view(), name="article_create"),
    path('watchlist/register/', WatchListRegister.as_view(), name="watchlist_register"),
    path('watchlist/edit/<int:pk>/', WatchListEdit.as_view(), name="watchlist_edit"),
    path('financial_results/', FinancialResultsListView.as_view(), name="financial_results"),
    path('financial_results/detail/<str:ticker>/', FinancialResultsDetailListView.as_view(), name="financial_results_detail"),
    path('financial_results/create/', FinancialResultsCreateView.as_view(), name="financial_results_create")
]
