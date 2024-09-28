from django.urls import path

from home.views import IndexView, PostDetailView, PostUpdateView, PostCreateView

app_name = "home"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("post/<int:pk>/", PostDetailView.as_view(), name="post_detail"),
    path("post/<int:pk>/update/", PostUpdateView.as_view(), name="post_update"),
    path("post/create/", PostCreateView.as_view(), name="post_create"),
]
