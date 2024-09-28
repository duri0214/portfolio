from django.urls import path

from home.views import IndexView, PostDetailView

app_name = "home"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("post/<int:pk>/", PostDetailView.as_view(), name="post_detail"),
]
