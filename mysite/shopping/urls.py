"""urls.py"""
from django.urls import path
from .views import IndexView, ProductDetailView, UploadSingleView, UploadBulkView

app_name = 'shp'
urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('product/edit/<int:mode>/', IndexView.as_view(), name='product_edit'),
    path('product/detail/<int:pk>/', ProductDetailView.as_view(), name='product_detail'),
    path('product/regist/single/', UploadSingleView.as_view(), name='product_register_single'),
    path('product/regist/bulk/', UploadBulkView.as_view(), name='product_register_bulk'),
    # path('staff/detail/<int:pk>/', StaffDetailView.as_view(), name='staff_detail')
]
