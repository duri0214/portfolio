from django.http import HttpResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (
    CreateView,
    ListView,
    UpdateView,
    DeleteView,
    DetailView,
)

from config.settings import MEDIA_ROOT
from hospital.domain.service.export_report import (
    ExportBillingService,
    VotingManagementService,
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
            return ElectionLedger.objects.filter(election=election).order_by(
                "-created_at"
            )
        return ElectionLedger.objects.all().order_by("-created_at")

    def get_context_data(self, **kwargs):
        election = self.request.GET.get("election")
        context = super().get_context_data(**kwargs)
        context["elections"] = Election.objects.all()
        context["canExport"] = True if election else False
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


class ExportBillingListView(View):
    @staticmethod
    def get(request, *args, **kwargs):
        election_id = request.GET.get("election", None)
        if not election_id:
            return HttpResponse("Election ID not provided", status=400)
        service = ExportBillingService(temp_folder=MEDIA_ROOT / "hospital/temp")
        return service.export(election_id)


class ExportVotingManagementListView(View):
    @staticmethod
    def get(request, *args, **kwargs):
        election_id = request.GET.get("election", None)
        if not election_id:
            return HttpResponse("Election ID not provided", status=400)
        service = VotingManagementService(temp_folder=MEDIA_ROOT / "hospital/temp")
        return service.export(election_id)
