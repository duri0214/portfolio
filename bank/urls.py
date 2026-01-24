from django.urls import path
from . import views

app_name = "bank"
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path(
        "analysis/mufg-living-cost/",
        views.MufgLivingCostAnalysisView.as_view(),
        name="mufg_analysis_living_cost",
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
