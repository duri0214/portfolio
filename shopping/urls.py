from django.urls import path

from .views import (
    IndexView,
    ProductDetailView,
    CreateSingleView,
    CreateBulkView,
    StaffDetailView,
    StaffEditView,
    StaffCreateView,
    ProductEditView,
    PaymentConfirmView,
)

app_name = "shp"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("product/edit/<int:pk>/", ProductEditView.as_view(), name="product_edit"),
    path(
        "product/detail/<int:pk>/", ProductDetailView.as_view(), name="product_detail"
    ),
    path(
        "product/create/single/",
        CreateSingleView.as_view(),
        name="product_create_single",
    ),
    path("product/create/bulk/", CreateBulkView.as_view(), name="product_create_bulk"),
    path("staff/detail/<int:pk>/", StaffDetailView.as_view(), name="staff_detail"),
    path(
        "payment/confirm/<int:pk>/",
        PaymentConfirmView.as_view(),
        name="payment_confirm",
    ),
    path("staff/edit/<int:pk>/", StaffEditView.as_view(), name="staff_edit"),
    path("staff/create/", StaffCreateView.as_view(), name="staff_create"),
]
