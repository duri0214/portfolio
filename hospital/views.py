from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    ListView,
    UpdateView,
    DeleteView,
    DetailView,
)

from hospital.forms import ElectionLedgerCreateForm, ElectionLedgerUpdateForm
from hospital.models import ElectionLedger, Election


class IndexView(ListView):
    model = ElectionLedger
    template_name = "hospital/index.html"
    paginate_by = 5
    ordering = ["-created_at"]

    def get_queryset(self):
        election = self.request.GET.get("election")
        if election:
            return ElectionLedger.objects.filter(election=election)
        return ElectionLedger.objects.all()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["elections"] = Election.objects.all()
        return context


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
