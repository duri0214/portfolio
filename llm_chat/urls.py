from django.urls import path

from .views import StreamResponseView, IndexView, StreamResultSaveView

app_name = "llm"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("stream/", StreamResponseView.as_view(), name="stream_response"),
    path(
        "stream/result_save/", StreamResultSaveView.as_view(), name="stream_result_save"
    ),
]
