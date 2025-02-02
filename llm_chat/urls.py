from django.urls import path

from .views import StreamResponseView, IndexView

app_name = "llm"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("stream/", StreamResponseView.as_view(), name="stream_response"),
]
