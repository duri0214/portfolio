from django.urls import reverse_lazy
from django.views.generic import CreateView, ListView

from hospital.forms import ElectionLedgerCreateForm
from hospital.models import ElectionLedger


class IndexView(ListView):
    model = ElectionLedger
    template_name = "hospital/index.html"
    paginate_by = 5


class ElectionLedgerCreateView(CreateView):
    form_class = ElectionLedgerCreateForm
    template_name = "hospital/election_ledger/create.html"
    success_url = reverse_lazy("hsp:index")
