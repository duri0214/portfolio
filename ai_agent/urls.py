from django.urls import path

from ai_agent.views import IndexView, SendMessageView

app_name = "agt"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("send/", SendMessageView.as_view(), name="send_message"),
]
