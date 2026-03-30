from django.urls import path

from usa_research.views import (
    IndexView,
    FinancialResultsListView,
    FinancialResultsDetailListView,
    FinancialResultsCreateView,
)

app_name = "usa"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
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
