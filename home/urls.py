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
)

app_name = "home"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("hospital/", HospitalIndexView.as_view(), name="hospital_index"),
    path("soil_analysis/", SoilAnalysisIndexView.as_view(), name="soil_analysis_index"),
    path(
        "vietnam_reserch/",
        VietnamResearchIndexView.as_view(),
        name="vietnam_research_index",
    ),
    path("gmarker/", GmarkerIndexView.as_view(), name="gmarker_index"),
    path("shopping/", ShoppingIndexView.as_view(), name="shopping_index"),
    path("rental_shop/", RentalShopIndexView.as_view(), name="rental_shop_index"),
    path("taxonomy/", TaxonomyIndexView.as_view(), name="taxonomy_index"),
    path("securities/", SecuritiesIndexView.as_view(), name="securities_index"),
    path("llm_chat/", LlmChatIndexView.as_view(), name="llm_chat_index"),
]
