from django.urls import path

from .views import (
    IndexView,
    ProductDetail,
    CreateSingle,
    CreateBulk,
    StaffDetail,
    StaffEdit,
    StaffCreate,
    ProductEdit,
)

app_name = "shp"
urlpatterns = [
    path("", IndexView.as_view(), name="index"),
    path("product/edit/<int:pk>/", ProductEdit.as_view(), name="product_edit"),
    path("product/detail/<int:pk>/", ProductDetail.as_view(), name="product_detail"),
    path(
        "product/create/single/",
        CreateSingle.as_view(),
        name="product_create_single",
    ),
    path("product/create/bulk/", CreateBulk.as_view(), name="product_create_bulk"),
    path("staff/detail/<int:pk>/", StaffDetail.as_view(), name="staff_detail"),
    path("staff/edit/<int:pk>/", StaffEdit.as_view(), name="staff_edit"),
    path("staff/create/", StaffCreate.as_view(), name="staff_create"),
]
