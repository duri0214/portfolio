from django.urls import path

from ai_agent.views import IndexView

app_name = "agt"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
]
