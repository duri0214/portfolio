from django.urls import path

app_name = "bot"
urlpatterns = [path("callback/", CallbackView.as_view(), name="callback")]
