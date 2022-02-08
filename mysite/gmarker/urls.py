"""urls.py"""
from django.urls import path
from . import views

app_name = 'mrk'
urlpatterns = [
    path('', views.index, name='index'),
    path('search/<str:search_code>', views.index, name='index_search'),
    path('search/detail/<str:place_id>', views.search_detail, name='detail_search'),
    path('result/<str:search_code>', views.index, name='index_result'),
]
