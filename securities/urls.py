from django.urls import path

from securities.views import IndexView

app_name = "securities"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
]
