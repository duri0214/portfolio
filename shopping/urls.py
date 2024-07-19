from django.urls import path

from .views import (
    Index,
    ProductDetail,
    UploadSingle,
    UploadBulk,
    StaffDetail,
    StaffEdit,
    StaffCreate,
    ProductEdit,
)

app_name = "shp"
urlpatterns = [
    path("", Index.as_view(), name="index"),
    path("product/edit/<int:pk>/", ProductEdit.as_view(), name="product_edit"),
    path("product/detail/<int:pk>/", ProductDetail.as_view(), name="product_detail"),
    path(
        "product/regist/single/",
        UploadSingle.as_view(),
        name="product_register_single",
    ),
    path("product/regist/bulk/", UploadBulk.as_view(), name="product_register_bulk"),
    path("staff/detail/<int:pk>/", StaffDetail.as_view(), name="staff_detail"),
    path("staff/edit/<int:pk>/", StaffEdit.as_view(), name="staff_edit"),
    path("staff/create/", StaffCreate.as_view(), name="staff_create"),
]
