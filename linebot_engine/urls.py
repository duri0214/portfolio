from django.urls import path

from linebot_engine.views import CallbackView

app_name = "bot"
urlpatterns = [path("callback/", CallbackView.as_view(), name="callback")]
