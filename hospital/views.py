import os
import uuid
from datetime import datetime
from pathlib import Path

from django.db import models
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
from openpyxl import Workbook

from config.settings import MEDIA_ROOT
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


def append_row(instance, ws):
    row = []
    for field in instance._meta.fields:
        if isinstance(field, models.ForeignKey):
            value = getattr(instance, f"{field.name}_id")
            if isinstance(value, datetime):
                value = value.replace(tzinfo=None)
        else:
            value = getattr(instance, field.name)
            if isinstance(value, datetime):
                value = value.replace(tzinfo=None)
        row.append(value)
    ws.append(row)


class ExportBillingListView(View):
    @staticmethod
    def get(request, *args, **kwargs):
        election_id = request.GET.get("election", None)
        if not election_id:
            return HttpResponse("Election ID not provided", status=400)

        print(f"Election ID: {election_id}")

        ledgers = ElectionLedger.objects.filter(election_id=election_id)

        wb = Workbook()
        ws = wb.active
        ws.append([field.name for field in ElectionLedger._meta.fields])

        temp_folder = Path(MEDIA_ROOT) / "hospital/temp"
        os.makedirs(temp_folder, exist_ok=True)
        unique_filename = f"{str(uuid.uuid4())}.xlsx"

        for ledger in ledgers:
            append_row(ledger, ws)

        wb.save(filename=temp_folder / unique_filename)
        try:
            with open(temp_folder / unique_filename, "rb") as f:
                excel_data = f.read()

            response = HttpResponse(
                excel_data,
                content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
            response["Content-Disposition"] = "attachment; filename=ElectionLedger.xlsx"
        finally:
            os.remove(temp_folder / unique_filename)
        return response
