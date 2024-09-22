from django.urls import path

from hospital.views import IndexView

app_name = "hsp"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
]
