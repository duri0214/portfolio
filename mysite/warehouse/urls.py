from django.urls import path

from .views import IndexView, ItemCreateView, ItemDetailView, InvoiceCreateView, InvoiceListView, InvoiceDetailView

app_name = 'war'
urlpatterns = [
    path('', IndexView.as_view(), name='index'),
    path('create/', ItemCreateView.as_view(), name='item_create'),
    path('detail/<int:pk>/', ItemDetailView.as_view(), name='item_detail'),
    path('choose/<int:pk>/', IndexView.as_view(), name='index_choose'),
    path('reset/', IndexView.as_view(), name='reset'),
    path('invoice/create/', InvoiceCreateView.as_view(), name='invoice_create'),
    path('invoice/list/', InvoiceListView.as_view(), name='invoice_list'),
    path('invoice/list/<int:mode>/', InvoiceListView.as_view(), name='invoice_list'),
    path('invoice/detail/<int:pk>/', InvoiceDetailView.as_view(), name='invoice_detail'),
]
