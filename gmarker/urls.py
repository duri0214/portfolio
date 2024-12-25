from django.urls import path

from . import views
from .views import SearchDetailView

app_name = "mrk"
urlpatterns = [
    path("", views.index, name="index"),
    path("search/<str:search_code>", views.index, name="nearby_search"),
    path(
        "search/detail/<str:place_id>", SearchDetailView.as_view(), name="detail_search"
    ),
]
