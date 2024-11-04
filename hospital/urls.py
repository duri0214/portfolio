from django.urls import path

from hospital.views import (
    IndexView,
    ElectionLedgerCreateView,
    ElectionLedgerUpdateView,
    ElectionLedgerDeleteView,
)

app_name = "hsp"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path(
        "election_ledger/create/",
        ElectionLedgerCreateView.as_view(),
        name="election_ledger_create",
    ),
    path(
        "election_ledger/update/<int:pk>/",
        ElectionLedgerUpdateView.as_view(),
        name="election_ledger_update",
    ),
    path(
        "election_ledger/delete/<int:pk>/",
        ElectionLedgerDeleteView.as_view(),
        name="election_ledger_delete",
    ),
]
