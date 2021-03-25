"""docstring"""
from django.urls import path
from . import views

app_name = 'vnm'
urlpatterns = [
    path('', views.index, name='index'),
    path('likes/<int:user_id>/<int:article_id>', views.likes, name='likes'),
    path('article/create/', views.ArticleCreateView.as_view(), name="article_create"),
    path('watchlist/register', views.WatchListRegister.as_view(), name="watchlist_register")
]
