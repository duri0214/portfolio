from django.urls import path
from . import views

app_name = "kokkai"
urlpatterns = [
    path("", views.IndexView.as_view(), name="index"),
    path("meeting/<int:pk>/", views.MeetingDetailView.as_view(), name="meeting_detail"),
]
