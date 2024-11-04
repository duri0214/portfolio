from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    ListView,
    UpdateView,
    DeleteView,
    DetailView,
)

from hospital.forms import ElectionLedgerCreateForm, ElectionLedgerUpdateForm
from hospital.models import ElectionLedger


class IndexView(ListView):
    model = ElectionLedger
    template_name = "hospital/index.html"
    paginate_by = 5


class ElectionLedgerCreateView(CreateView):
    form_class = ElectionLedgerCreateForm
    template_name = "hospital/election_ledger/create.html"
    success_url = reverse_lazy("hsp:index")


class ElectionLedgerUpdateView(UpdateView):
    model = ElectionLedger
    form_class = ElectionLedgerUpdateForm
    template_name = "hospital/election_ledger/update.html"
    success_url = reverse_lazy("hsp:index")


class ElectionLedgerDeleteView(DeleteView):
    model = ElectionLedger
    template_name = "hospital/election_ledger/delete.html"
    success_url = reverse_lazy("hsp:index")


class ElectionLedgerDetailView(DetailView):
    model = ElectionLedger
    template_name = "hospital/election_ledger/detail.html"
