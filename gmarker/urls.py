from django.urls import path

from gmarker.views import IndexView

app_name = "mrk"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("search/<int:search_code>", IndexView.as_view(), name="nearby_search"),
]
