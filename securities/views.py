from dateutil.relativedelta import relativedelta
from django.urls import reverse_lazy
from django.utils.timezone import now
from django.views.generic import TemplateView, FormView

from securities.domain.service.upload import UploadService
from securities.forms import UploadForm


class IndexView(TemplateView):
    template_name = "securities/report/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        current_time = now()
        context["start_date"] = current_time - relativedelta(years=1)  # 1 year ago
        context["end_date"] = current_time - relativedelta(days=1)  # yesterday

        return context

    @staticmethod
    def post(request, **kwargs):
        start_date = request.POST.get("start_date")
        end_date = request.POST.get("end_date")
        print(f"開始日: {start_date}, 終了日: {end_date}")
        pass


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
