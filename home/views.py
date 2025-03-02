from django.views.generic import TemplateView


class IndexView(TemplateView):
    template_name = "home/index.html"


class HospitalIndexView(TemplateView):
    template_name = "home/hospital/index.html"


class SoilAnalysisIndexView(TemplateView):
    template_name = "home/soil_analysis/index.html"


class VietnamResearchIndexView(TemplateView):
    template_name = "home/vietnam_research/index.html"


class GmarkerIndexView(TemplateView):
    template_name = "home/gmarker/index.html"


class ShoppingIndexView(TemplateView):
    template_name = "home/shopping/index.html"


class RentalShopIndexView(TemplateView):
    template_name = "home/rental_shop/index.html"


class TaxonomyIndexView(TemplateView):
    template_name = "home/taxonomy/index.html"


class SecuritiesIndexView(TemplateView):
    template_name = "home/securities/index.html"


class LlmChatIndexView(TemplateView):
    template_name = "home/llm_chat/index.html"


class AiAgentIndexView(TemplateView):
    template_name = "home/ai_agent/index.html"


class JpStocksIndexView(TemplateView):
    template_name = "home/jp_stocks/index.html"
