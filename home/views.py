from django.views.generic import TemplateView


class IndexView(TemplateView):
    template_name = "home/index.html"


class HospitalIndexView(TemplateView):
    template_name = "home/hospital/index.html"


class SoilAnalysisIndexView(TemplateView):
    template_name = "home/soil_analysis/index.html"
