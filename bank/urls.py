from django.urls import path
from . import views

app_name = "bank"
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("accounts/", views.BankAccountManageView.as_view(), name="bank_account_manage"),
    path(
        "accounts/sample-csv/",
        views.BankAccountSampleCsvDownloadView.as_view(),
        name="bank_account_sample_csv",
    ),
    path(
        "analysis/mufg-living-cost/",
        views.MufgLivingCostAnalysisView.as_view(),
        name="mufg_analysis_living_cost",
    ),
    path(
        "analysis/mufg-category-monthly/",
        views.MufgCategoryMonthlyAnalysisView.as_view(),
        name="mufg_analysis_category_monthly",
    ),
    path(
        "upload/mufg-deposit/",
        views.MufgDepositUploadView.as_view(),
        name="mufg_deposit_upload",
    ),
    path(
        "upload/mufg-deposit/delete/",
        views.MufgDepositDeleteView.as_view(),
        name="mufg_deposit_delete",
    ),
]
