from django.urls import path

from hospital.views import IndexView, ElectionLedgerCreateView

app_name = "hsp"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path(
        "election_ledger/create/",
        ElectionLedgerCreateView.as_view(),
        name="election_ledger_create",
    ),
]
