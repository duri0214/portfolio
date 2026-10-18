from django.urls import path

from gmarker.views import CandidateSearchView, CoordinateRegisterView, IndexView

app_name = "mrk"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("coord/create/", CoordinateRegisterView.as_view(), name="coordinate_create"),
    path(
        "candidates/<slug:criteria_slug>/",
        CandidateSearchView.as_view(),
        name="candidate_search",
    ),
    path(
        "craft-beer-candidates/",
        CandidateSearchView.as_view(default_criteria_slug="shibuya-craft-beer"),
        name="craft_beer_candidates",
    ),
    path("search/<int:search_code>", IndexView.as_view(), name="nearby_search"),
]
