from django.urls import path

from home.views import (
    IndexView,
    HospitalIndexView,
    SoilAnalysisIndexView,
    VietnamResearchIndexView,
    GmarkerIndexView,
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
    path(
        "gmarker/",
        GmarkerIndexView.as_view(),
        name="gmarker_index",
    ),
]
