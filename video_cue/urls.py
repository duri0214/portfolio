from django.urls import path

from video_cue import views

app_name = "video_cue"
urlpatterns = [
    path("", views.index, name="index"),
    path("api/results/<slug:key>/", views.upload, name="upload"),
    path("<slug:key>/", views.detail, name="detail"),
    path("<slug:key>/media/highlight/", views.media, name="media"),
]
