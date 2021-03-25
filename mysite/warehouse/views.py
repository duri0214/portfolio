from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView, CreateView, DetailView, ListView
from sqlalchemy import create_engine

from .forms import RegisterForm, InvoiceForm
from .models import Warehouse, Item, RentalStatus, Invoice, Staff, BillingStatus
import pandas as pd
import numpy as np


class IndexView(TemplateView):
    """IndexView"""
    template_name = 'warehouse/index.html'

    def post(self, request, *args, **kwargs):
        if request.path == '/warehouse/reset/':
            # reset
            Item.objects.filter(rental_status=RentalStatus.objects.get(pk=4)).update(rental_status=RentalStatus(id=1))
        else:
            # choose
            item = Item.objects.get(pk=self.kwargs['pk'])
            item.rental_status = RentalStatus(id=4)
            item.save()
        return redirect('war:index')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        warehouse = Warehouse.objects.get(pk=Staff.objects.get(pk=1).warehouse_id)  # TODO: ユーザー情報から倉庫を取得
        _con = create_engine('mysql+mysqldb://python:python123@127.0.0.1/pythondb', echo=False).connect()

        # shelf
        data = pd.read_sql_query(
            '''
            SELECT
                pos_y, pos_x, GROUP_CONCAT(name) items
            FROM pythondb.warehouse_item
            WHERE rental_status_id = 1 -- available
            GROUP BY pos_y, pos_x
            ''', _con)
        array = np.zeros((warehouse.height, warehouse.width), dtype=int)
        for idx, row in data.iterrows():
            # pos_y, pos_x は 1base
            array[row['pos_y']-1, row['pos_x']-1] = len(row['items'].split(','))

        # item list
        available_items = Item.objects.filter(warehouse_id=warehouse.id).filter(rental_status_id=1)
        non_available_items = Item.objects.filter(warehouse_id=warehouse.id).filter(rental_status_id__gt=1)

        context['shelf'] = array[::-1]
        context['available_items'] = available_items
        context['non_available_items'] = non_available_items
        return context


class ItemDetailView(DetailView):
    model = Item


class ItemRegisterView(CreateView):
    template_name = 'warehouse/register.html'
    model = Item
    form_class = RegisterForm

    def form_valid(self, form):
        form = form.save(commit=False)
        form.rental_status = RentalStatus(id=1)  # available
        form.save()
        return redirect('war:register')

    def form_invalid(self, form):
        messages.add_message(self.request, messages.WARNING, form.errors)
        return super().form_invalid(form)


class InvoiceCreateView(CreateView):
    template_name = 'warehouse/invoice_create.html'
    model = Invoice
    form_class = InvoiceForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        warehouse = Warehouse.objects.get(pk=Staff.objects.get(pk=1).warehouse_id)  # TODO: ユーザー情報から倉庫を取得
        context['invoice_items'] = Item.objects.filter(warehouse_id=warehouse.id).filter(rental_status_id=4)
        return context

    def get_success_url(self):
        Item.objects.filter(rental_status=RentalStatus.objects.get(pk=4)).update(
            invoice=self.object.id,
            rental_status=RentalStatus(id=2)
        )
        return reverse('war:index')


class InvoiceListView(ListView):
    template_name = 'warehouse/invoice_list.html'
    model = Invoice

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['billing_status'] = BillingStatus.objects.get(pk=self.kwargs['mode'])
        return context

    def get_queryset(self, **kwargs):
        return Invoice.objects.filter(billing_status_id=BillingStatus.objects.get(pk=self.kwargs['mode']))
