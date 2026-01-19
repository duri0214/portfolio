from django.urls import path
from . import views

app_name = "bank"
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path(
        "upload/mufg-deposit/",
        views.MufgDepositUploadView.as_view(),
        name="mufg_deposit_upload",
    ),
]
