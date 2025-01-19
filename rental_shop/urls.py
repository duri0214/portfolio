from django.urls import path

from .views import (
    IndexView,
    ItemCreateView,
    ItemDetailView,
    InvoiceCreateView,
    InvoiceListView,
    InvoiceDetailView,
    RentItemView,
    ResetRentalsView,
)

app_name = "ren"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("create/", ItemCreateView.as_view(), name="item_create"),
    path("detail/<int:pk>/", ItemDetailView.as_view(), name="item_detail"),
    path(
        "rent/<int:item_id>/",
        RentItemView.as_view(),
        name="rent_item",
    ),
    path(
        "reset/<int:warehouse_id>/",
        ResetRentalsView.as_view(),
        name="reset_items",
    ),
    path("invoice/create/", InvoiceCreateView.as_view(), name="invoice_create"),
    path("invoice/list/", InvoiceListView.as_view(), name="invoice_list"),
    path("invoice/list/<int:mode>/", InvoiceListView.as_view(), name="invoice_list"),
    path(
        "invoice/detail/<int:pk>/", InvoiceDetailView.as_view(), name="invoice_detail"
    ),
]
