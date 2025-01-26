from django.urls import path

from home.views import (
    IndexView,
    HospitalIndexView,
    SoilAnalysisIndexView,
)

app_name = "home"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("hospital/", HospitalIndexView.as_view(), name="hospital_index"),
    path("soil_analysis/", SoilAnalysisIndexView.as_view(), name="soil_analysis_index"),
]
