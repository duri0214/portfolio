from django.urls import path

from home.views import (
    IndexView,
    HospitalIndexView,
    SoilAnalysisIndexView,
    VietnamResearchIndexView,
    GmarkerIndexView,
    ShoppingIndexView,
    RentalShopIndexView,
    TaxonomyIndexView,
    SecuritiesIndexView,
    LlmChatIndexView,
    AiAgentIndexView,
    JpStocksIndexView,
    WelfareServicesIndexView,
    UsaResearchIndexView,
    KokkaiIndexView,
)

app_name = "home"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("about/hospital/", HospitalIndexView.as_view(), name="about_hospital"),
    path(
        "about/soil_analysis/",
        SoilAnalysisIndexView.as_view(),
        name="about_soil_analysis",
    ),
    path(
        "about/vietnam_research/",
        VietnamResearchIndexView.as_view(),
        name="about_vietnam_research",
    ),
    path(
        "about/usa_research/",
        UsaResearchIndexView.as_view(),
        name="about_usa_research",
    ),
    path("about/gmarker/", GmarkerIndexView.as_view(), name="about_gmarker"),
    path("about/shopping/", ShoppingIndexView.as_view(), name="about_shopping"),
    path("about/rental_shop/", RentalShopIndexView.as_view(), name="about_rental_shop"),
    path("about/taxonomy/", TaxonomyIndexView.as_view(), name="about_taxonomy"),
    path("about/securities/", SecuritiesIndexView.as_view(), name="about_securities"),
    path("about/llm_chat/", LlmChatIndexView.as_view(), name="about_llm_chat"),
    path("about/ai_agent/", AiAgentIndexView.as_view(), name="about_ai_agent"),
    path("about/jp_stocks/", JpStocksIndexView.as_view(), name="about_jp_stocks"),
    path(
        "about/welfare_services/",
        WelfareServicesIndexView.as_view(),
        name="about_welfare_services",
    ),
    path("about/kokkai/", KokkaiIndexView.as_view(), name="about_kokkai"),
]
