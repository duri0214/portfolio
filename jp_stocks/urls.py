from django.urls import path

from jp_stocks.views import (
    IndexView,
    OrderBookListView,
    CreateOrderView,
    RokunohePdfDownloadView,
)

app_name = "jpn"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path(
        "rokunohe-pdf-download/",
        RokunohePdfDownloadView.as_view(),
        name="rokunohe_pdf_download",
    ),
    path("create-order/", CreateOrderView.as_view(), name="create_order"),
    path("order-book/", OrderBookListView.as_view(), name="order_book"),
]
