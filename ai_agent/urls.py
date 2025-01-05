from django.urls import path

from ai_agent.views import (
    IndexView,
    StartConversationView,
    ConversationDetailView,
    SendMessageView,
)

app_name = "agt"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("start/", StartConversationView.as_view(), name="start_conversation"),
    path(
        "conversation/<int:pk>/",
        ConversationDetailView.as_view(),
        name="conversation_detail",
    ),
    path("conversation/<int:pk>/send/", SendMessageView.as_view(), name="send_message"),
]
