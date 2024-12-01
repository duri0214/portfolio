from django.urls import path

from hospital.views import (
    IndexView,
    ElectionLedgerCreateView,
    ElectionLedgerUpdateView,
    ElectionLedgerDeleteView,
    ElectionLedgerDetailView,
    ExportBillingListView,
    ExportVotingManagementListView,
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
    path(
        "election_ledger/<int:pk>/detail/",
        ElectionLedgerDetailView.as_view(),
        name="election_ledger_detail",
    ),
    path(
        "export/billing-list/",
        ExportBillingListView.as_view(),
        name="export_billing_list",
    ),
    path(
        "export/voting-management-list/",
        ExportVotingManagementListView.as_view(),
        name="export_voting_management_list",
    ),
]
