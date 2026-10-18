from django.urls import path

from gmarker.views import CraftBeerCandidateView, CoordinateRegisterView, IndexView

app_name = "mrk"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("coord/create/", CoordinateRegisterView.as_view(), name="coordinate_create"),
    path(
        "craft-beer-candidates/",
        CraftBeerCandidateView.as_view(),
        name="craft_beer_candidates",
    ),
    path("search/<int:search_code>", IndexView.as_view(), name="nearby_search"),
]
