from django.conf import settings
from django.conf.urls.static import static
from django.urls import path

from . import views

app_name = "soil"
urlpatterns = [
    path("", views.Home.as_view(), name="home"),
    path("company/list", views.CompanyListView.as_view(), name="company_list"),
    path("company/create", views.CompanyCreateView.as_view(), name="company_create"),
    path(
        "company/<int:pk>/detail",
        views.CompanyDetailView.as_view(),
        name="company_detail",
    ),
    path(
        "company/<int:company_id>/land/list",
        views.LandListView.as_view(),
        name="land_list",
    ),
    path(
        "company/<int:company_id>/land/create",
        views.LandCreateView.as_view(),
        name="land_create",
    ),
    path("prefectures/", views.PrefecturesView.as_view(), name="prefectures"),
    path(
        "api/land/location/info",
        views.LocationInfoView.as_view(),
        name="land_location_info",
    ),
    path(
        "prefecture/<int:prefecture_id>/cities",
        views.PrefectureCitiesView.as_view(),
        name="prefecture_cities",
    ),
    path(
        "company/<int:company_id>/land/<int:pk>/detail",
        views.LandDetailView.as_view(),
        name="land_detail",
    ),
    path(
        "company/<int:company_id>/land_ledger/<int:land_ledger_id>/land_report_chemical",
        views.LandReportChemicalListView.as_view(),
        name="land_report_chemical",
    ),
    path(
        "hardness/upload",
        views.HardnessUploadView.as_view(),
        name="hardness_upload",
    ),
    path(
        "hardness/success",
        views.HardnessSuccessView.as_view(),
        name="hardness_success",
    ),
    path(
        "hardness/association",
        views.HardnessAssociationView.as_view(),
        name="hardness_association",
    ),
    path(
        "hardness/association/field_group/<int:memory_anchor>",
        views.HardnessAssociationFieldGroupView.as_view(),
        name="hardness_association_field_group",
    ),
    path(
        "hardness/association/individual/<int:memory_anchor>/<int:land_ledger>",
        views.HardnessAssociationIndividualView.as_view(),
        name="hardness_association_individual",
    ),
    path(
        "hardness/association/success",
        views.HardnessAssociationSuccessView.as_view(),
        name="hardness_association_success",
    ),
    path(
        "route_suggest/upload",
        views.RouteSuggestUploadView.as_view(),
        name="route_suggest_upload",
    ),
    path(
        "route_suggest/ordering",
        views.RouteSuggestOrderingView.as_view(),
        name="route_suggest_ordering",
    ),
    path(
        "route_suggest/success",
        views.RouteSuggestSuccessView.as_view(),
        name="route_suggest_success",
    ),
    path(
        "picture/land/associate",
        views.AssociatePictureAndLandView.as_view(),
        name="associate_picture_and_land",
    ),
    path(
        "picture/land/associate/result",
        views.AssociatePictureAndLandResultView.as_view(),
        name="associate_picture_and_land_result",
    ),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
