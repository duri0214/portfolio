from django.urls import path

from jp_stocks.views import IndexView, OrderBookListView, CreateOrderView

app_name = "jpn"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("create-order/", CreateOrderView.as_view(), name="create_order"),
    path("order-book/", OrderBookListView.as_view(), name="order_book"),
]
