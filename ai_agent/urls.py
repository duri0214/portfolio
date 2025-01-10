from django.urls import path

from ai_agent.views import IndexView, NextTurnView

app_name = "agt"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("next_turn/", NextTurnView.as_view(), name="next_turn"),
]
