"""urls.py"""
from django.urls import path
from . import views

app_name = 'mrk'
urlpatterns = [
    path('', views.index, name='index'),
    path('search/<str:searchcode>', views.index, name='index_search'),
    path('search/detail/<str:place_id>', views.searchdetail, name='detail_search'),
    path('result/<str:searchcode>', views.index, name='index_result'),
]
