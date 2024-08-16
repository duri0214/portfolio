from django.urls import path

from securities.views import (
    IndexView,
    EdinetCodeUploadView,
    EdinetCodeUploadSuccessView,
    DownloadReserveView,
    CountingView,
)

app_name = "securities"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("download_reserve/", DownloadReserveView.as_view(), name="download_reserve"),
    path("table_view/counting", CountingView.as_view(), name="counting"),
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
