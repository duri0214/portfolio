from datetime import datetime
from pathlib import Path

from dateutil.relativedelta import relativedelta
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.utils.timezone import now
from django.views.generic import TemplateView, FormView, ListView

from config import settings
from securities.domain.service.upload import UploadService
from securities.domain.service.xbrl import XbrlService
from securities.domain.valueobject.edinet import RequestData
from securities.forms import UploadForm
from securities.models import ReportDocument


class IndexView(ListView):
    template_name = "securities/report/index.html"
    model = ReportDocument
    paginate_by = 10

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.values(
            "doc_id",
            "edinet_code",
            "sec_code",
            "jcn",
            "filer_name",
            "period_start",
            "period_end",
            "submit_date_time",
            "doc_description",
            "xbrl_flag",
        ).order_by("doc_id")
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_time = now()
        context["start_date"] = current_time - relativedelta(years=1)  # 1 year ago
        context["end_date"] = current_time - relativedelta(days=1)  # yesterday

        return context

    @staticmethod
    def post(request, **kwargs):
        ReportDocument.objects.all().delete()

        start_date_str = request.POST.get("start_date")
        end_date_str = request.POST.get("end_date")
        start_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d").date()
        home_dir = settings.MEDIA_ROOT  # TODO: XbrlServiceのinitからwork_dirを削除して
        service = XbrlService(work_dir=Path(home_dir, "xbrlReport"))
        report_document_list = service.fetch_report_doc_list(
            RequestData(start_date=start_date, end_date=end_date)
        )
        ReportDocument.objects.bulk_create(report_document_list)
        return redirect("securities:index")


class EdinetCodeUploadView(FormView):
    template_name = "securities/edinet_code_upload/form.html"
    form_class = UploadForm
    success_url = reverse_lazy("securities:edinet_code_upload_success")

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
