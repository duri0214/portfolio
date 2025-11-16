from django.urls import path

from usa_research.views import (
    IndexView,
)

app_name = "usa"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
]
