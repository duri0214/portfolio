from django.urls import path
from django.views.decorators.http import require_POST

from .views import IndexView, ItemRegisterView, ItemDetailView, InvoiceCreateView, InvoiceListView

app_name = 'war'
urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('register/', ItemRegisterView.as_view(), name='register'),
    path('detail/<int:pk>/', ItemDetailView.as_view(), name='detail'),
    path('choose/<int:pk>/', require_POST(IndexView.as_view()), name='index_choose'),
    path('reset/', require_POST(IndexView.as_view()), name='reset'),
    path('invoice/create/', InvoiceCreateView.as_view(), name='invoice_create'),
    path('invoice/inquiry/<int:mode>/', InvoiceListView.as_view(), name='invoice_inquiry'),
]
