from django.urls import path

from . import views

app_name = "welfare_services"

urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path(
        "fetch-facilities/",
        views.FetchFacilitiesView.as_view(),
        name="fetch_facilities",
    ),
    path(
        "facility-availability/create/",
        views.FacilityAvailabilityCreateView.as_view(),
        name="facility_availability_create",
    ),
    path(
        "facility-availability/complete/",
        views.FacilityAvailabilityCompleteView.as_view(),
        name="facility_availability_complete",
    ),
    path("facilities/", views.FacilityListView.as_view(), name="facility_list"),
    path(
        "facilities/<int:pk>/",
        views.FacilityDetailView.as_view(),
        name="facility_detail",
    ),
]
