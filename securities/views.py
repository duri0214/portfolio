import json
from datetime import datetime

from dateutil.relativedelta import relativedelta
from django.core.exceptions import ObjectDoesNotExist
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.utils.timezone import now
from django.views import View
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.generic import TemplateView, FormView, ListView

from securities.domain.service.upload import UploadService
from securities.domain.service.xbrl import XbrlService
from securities.domain.valueobject.edinet import RequestData
from securities.forms import UploadForm
from securities.models import ReportDocument, Company, Counting


class IndexView(ListView):
    template_name = "securities/index.html"
    model = ReportDocument
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.GET.get("reserved") == "yes":
            queryset = queryset.filter(download_reserved=True)
        else:
            queryset = queryset.filter(download_reserved=False)
        queryset = queryset.order_by("doc_id")
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_time = now()
        context["start_date"] = current_time - relativedelta(months=2)  # 2 months ago
        context["end_date"] = current_time - relativedelta(days=1)  # yesterday

        return context

    @staticmethod
    def post(request, **kwargs):
        if not Company.objects.exists():
            return redirect("sec:index")

        ReportDocument.objects.all().delete()

        start_date_str = request.POST.get("start_date")
        end_date_str = request.POST.get("end_date")
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        service = XbrlService()
        report_document_list = service.fetch_report_doc_list(
            RequestData(start_date=start_date, end_date=end_date)
        )
        ReportDocument.objects.bulk_create(report_document_list)
        return redirect("sec:index")


class CountingView(ListView):
    template_name = "securities/table_view/counting.html"
    model = Counting
    paginate_by = 10
    ordering = ["id"]


@method_decorator(ensure_csrf_cookie, name="dispatch")
class DownloadReserveView(View):
    @staticmethod
    def post(request):
        ids = json.loads(request.body)
        for identifier in ids:
            try:
                doc = ReportDocument.objects.get(pk=identifier)
                doc.download_reserved = True
                doc.save()
            except ObjectDoesNotExist:
                return JsonResponse(
                    {"error": f"No ReportDocument exists with ID {identifier}"},
                    status=400,
                )
        return JsonResponse({"status": "success"})


class EdinetCodeUploadView(FormView):
    template_name = "securities/edinet_code_upload/form.html"
    form_class = UploadForm
    success_url = reverse_lazy("sec:edinet_code_upload_success")

    def form_valid(self, form):
        service = UploadService(self.request)
        service.upload()
        return super().form_valid(form)


class EdinetCodeUploadSuccessView(TemplateView):
    template_name = "securities/edinet_code_upload/success.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # context["import_errors"] = SoilHardnessMeasurementImportErrors.objects.all()
        return context
