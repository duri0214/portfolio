from django.urls import path

from apache_access.views import IndexView


app_name = "apache_access"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
]
