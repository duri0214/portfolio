from django.shortcuts import render
from django.views.generic import TemplateView

from securities.domain.service.xbrl import SecuritiesReportService


class IndexView(TemplateView):
    template_name = "securities/report/index.html"

    def get(self, request, *args, **kwargs):
        securities_report_service = SecuritiesReportService()

        return render(request, self.template_name, securities_report_service.to_dict())
