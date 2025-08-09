from django.urls import path

from ai_agent.views import IndexView, NextTurnView, ResetTurnView

app_name = "agt"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("reset_turn/", ResetTurnView.as_view(), name="reset_turn"),
    path("next_turn/", NextTurnView.as_view(), name="next_turn"),
]
