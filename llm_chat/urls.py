from django.urls import path

from .views import (
    StreamingResponseView,
    IndexView,
    StreamResultSaveView,
    SyncResponseView,
)

app_name = "llm"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("streaming/", StreamingResponseView.as_view(), name="streaming_response"),
    path("sync/", SyncResponseView.as_view(), name="sync_response"),
    path(
        "streaming/result_save/",
        StreamResultSaveView.as_view(),
        name="streaming_result_save",
    ),
]
