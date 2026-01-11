from django.views.generic import TemplateView


class IndexView(TemplateView):
    template_name = "kokkai/index.html"
