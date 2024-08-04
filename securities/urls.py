from django.urls import path

from securities.views import (
    IndexView,
    EdinetCodeUploadView,
    EdinetCodeUploadSuccessView,
    DownloadView,
)

app_name = "securities"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("download/<str:doc_id>/", DownloadView.as_view(), name="download"),
    path(
        "edinet_code_upload/upload",
        EdinetCodeUploadView.as_view(),
        name="edinet_code_upload",
    ),
    path(
        "edinet_code_upload/success",
        EdinetCodeUploadSuccessView.as_view(),
        name="edinet_code_upload_success",
    ),
]
