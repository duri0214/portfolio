from django.urls import path

from gmarker.views import SearchDetailView, IndexView

app_name = "mrk"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("search/<int:search_code>", IndexView.as_view(), name="nearby_search"),
    path(
        "search/detail/<str:place_id>", SearchDetailView.as_view(), name="detail_search"
    ),
]
