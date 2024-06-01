from django.shortcuts import render
from django.urls import reverse_lazy
from django.views.generic import TemplateView, FormView

from securities.domain.service.upload import UploadService
from securities.forms import UploadForm


class IndexView(TemplateView):
    template_name = "securities/report/index.html"

    def get(self, request, *args, **kwargs):
        # xbrl_service = XbrlService()
        d = {}  # xbrl_service.to_dict()

        return render(request, self.template_name, d)


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
