from django.urls import path
from . import views

app_name = "kokkai"
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path(
        "reading-support/",
        views.ReadingSupportManagementView.as_view(),
        name="reading_support_management",
    ),
    path(
        "reading-support/entries/<int:pk>/edit/",
        views.ReadingSupportEntryUpdateView.as_view(),
        name="reading_support_entry_update",
    ),
    path(
        "reading-support/entries/<int:pk>/delete/",
        views.ReadingSupportEntryDeleteView.as_view(),
        name="reading_support_entry_delete",
    ),
    path(
        "reading-support/csv-import/",
        views.ReadingSupportCsvImportView.as_view(),
        name="reading_support_csv_import",
    ),
    path("meeting/<int:pk>/", views.MeetingDetailView.as_view(), name="meeting_detail"),
    path(
        "scenario/<int:scenario_id>/actors/",
        views.ScenarioActorSelectView.as_view(),
        name="scenario_actor_select",
    ),
    path(
        "scenario/play/<uuid:play_id>/",
        views.ScenarioGameView.as_view(),
        name="scenario_game",
    ),
    path(
        "scenario/play/<uuid:play_id>/result/",
        views.ScenarioResultView.as_view(),
        name="scenario_result",
    ),
]
