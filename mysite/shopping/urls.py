"""urls.py"""
from django.urls import path
from .views import IndexView, ProductDetailView, UploadSingleView, UploadBulkView

app_name = 'shp'
urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('detail/<int:pk>/', ProductDetailView.as_view(), name='detail'),
    path('regist/single/', UploadSingleView.as_view(), name='register_single'),
    path('regist/bulk/', UploadBulkView.as_view(), name='register_bulk'),
    path('edit/<int:mode>/', IndexView.as_view(), name='edit_data')
]
