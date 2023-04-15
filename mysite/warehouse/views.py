from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView, CreateView, DetailView, ListView
from sqlalchemy import create_engine, text

from .forms import ItemCreateForm, InvoiceCreateForm
from .models import Warehouse, Item, RentalStatus, Invoice, Staff, BillingStatus
import pandas as pd
import numpy as np


class IndexView(TemplateView):
    template_name = 'warehouse/index.html'

    @staticmethod
    def post(request, *args, **kwargs):
        if request.path == '/warehouse/reset/':
            # reset all rentals
            update_records = []
            items = Item.objects.filter(rental_status_id=RentalStatus.RENTAL)
            for item in items:
                item.rental_status_id = RentalStatus.STOCK
                update_records.append(item)
            if len(update_records) > 0:
                Item.objects.bulk_update(update_records, ['rental_status_id'])
        else:
            # rent an item
            item = Item.objects.get(pk=kwargs.get('pk'))
            item.rental_status = RentalStatus.objects.get(pk=RentalStatus.RENTAL)
            item.save()

        return redirect('war:index')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        warehouse = Warehouse.objects.get(pk=Staff.objects.get(pk=1).warehouse_id)  # TODO: ユーザー情報から倉庫を取得
        _con = create_engine('mysql+mysqldb://python:python123@127.0.0.1/portfolio_db', echo=False).connect()

        # TODO: 段・列でグループ化してアイテム名をカンマ区切りにする、みたいのがやりたいみたい
        data = pd.read_sql_query(text(
            '''
            SELECT
                pos_y, pos_x, GROUP_CONCAT(name) items
            FROM warehouse_item
            WHERE rental_status_id = 1 -- available
            GROUP BY pos_y, pos_x
            '''), _con)
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
    template_name = 'warehouse/item/detail.html'
    model = Item


class ItemCreateView(CreateView):
    template_name = 'warehouse/item/create.html'
    model = Item
    form_class = ItemCreateForm

    def form_valid(self, form):
        form = form.save(commit=False)
        form.rental_status = RentalStatus(id=1)  # available
        form.save()
        return redirect('war:item_create')

    def form_invalid(self, form):
        messages.add_message(self.request, messages.WARNING, form.errors)
        return super().form_invalid(form)


class InvoiceCreateView(CreateView):
    template_name = 'warehouse/invoice/create.html'
    model = Invoice
    form_class = InvoiceCreateForm

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        staff = Staff.objects.get(pk=1)
        warehouse = Warehouse.objects.get(pk=staff.warehouse_id)  # TODO: ユーザー情報から倉庫を取得
        context['invoice_items'] = Item.objects.filter(warehouse_id=warehouse.id, rental_status=RentalStatus.RENTAL)
        return context

    def get_success_url(self):
        rental_status = RentalStatus.objects.get(pk=RentalStatus.RENTAL)
        # 貸出中の関連アイテムに請求書を紐づける TODO: どの請求先企業の関連アイテム？の絞りが未対応
        Item.objects.filter(rental_status=rental_status).update(invoice=self.object.id)
        return reverse('war:invoice_detail', kwargs={'pk': self.object.pk})


class InvoiceDetailView(DetailView):
    template_name = 'warehouse/invoice/detail.html'
    model = Invoice
    context_object_name = 'invoice'


class InvoiceListView(ListView):
    template_name = 'warehouse/invoice/list.html'
    model = Invoice

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['billing_status'] = BillingStatus.objects.get(pk=self.kwargs['mode'])

        return context

    def get_queryset(self, **kwargs):
        billing_status = BillingStatus.objects.get(pk=self.kwargs['mode'])
        return Invoice.objects.filter(billing_status=billing_status)
