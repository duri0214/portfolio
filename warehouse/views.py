from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView, CreateView, DetailView, ListView

from warehouse.domain.repository.warehouse import get_item_position_counts
from warehouse.domain.valueobject.warehouse import Shelf, Warehouse, ShelfRow, ShelfCell
from warehouse.forms import ItemCreateForm, InvoiceCreateForm
from warehouse.models import Item, RentalStatus, Invoice, Staff, BillingStatus


class IndexView(TemplateView):
    template_name = "warehouse/index.html"

    @staticmethod
    def post(request, *args, **kwargs):
        if request.path == "/warehouse/reset/":
            # reset all rentals
            update_records = []
            items = Item.objects.filter(rental_status_id=RentalStatus.RENTAL)
            for item in items:
                item.rental_status_id = RentalStatus.STOCK
                update_records.append(item)
            if len(update_records) > 0:
                Item.objects.bulk_update(update_records, ["rental_status_id"])
        else:
            # rent an item
            item = Item.objects.get(pk=kwargs.get("pk"))
            item.rental_status = RentalStatus.objects.get(pk=RentalStatus.RENTAL)
            item.save()

        return redirect("war:index")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        staff = Staff.objects.get(pk=1)
        warehouse_list = staff.warehouses.all()

        warehouse_vos = []
        for warehouse in warehouse_list:
            item_position_counts = get_item_position_counts(warehouse.id)

            shelf_rows = []
            for _ in range(warehouse.height):
                # Create a ShelfRow with width number of ShelfCells, initialized with zero items.
                shelf_row = ShelfRow(
                    cells=[ShelfCell(item_count=0) for _ in range(warehouse.width)]
                )
                shelf_rows.append(shelf_row)

            for item_position_count in item_position_counts:
                # Update the corresponding ShelfCell with the correct item count.
                shelf_rows[item_position_count["pos_y"] - 1].cells[
                    item_position_count["pos_x"] - 1
                ].item_count = item_position_count["num_items"]

            available_items = Item.objects.filter(
                warehouse_id=warehouse.id, rental_status_id=RentalStatus.STOCK
            )
            non_available_items = Item.objects.filter(
                warehouse_id=warehouse.id
            ).exclude(rental_status_id=RentalStatus.STOCK)

            warehouse_vos.append(
                Warehouse(
                    warehouse=warehouse,
                    shelves=[Shelf(rows=shelf_rows)],  # TODO: いまは要素1しかない
                    available_items=available_items,
                    non_available_items=non_available_items,
                )
            )

        context["warehouses"] = warehouse_vos

        return context


class ItemDetailView(DetailView):
    template_name = "warehouse/item/detail.html"
    model = Item


class ItemCreateView(CreateView):
    template_name = "warehouse/item/create.html"
    model = Item
    form_class = ItemCreateForm

    def form_valid(self, form):
        form = form.save(commit=False)
        form.rental_status = RentalStatus(id=1)  # available
        form.save()
        return redirect("war:item_create")

    def form_invalid(self, form):
        messages.add_message(self.request, messages.WARNING, form.errors)
        return super().form_invalid(form)


class InvoiceCreateView(CreateView):
    template_name = "warehouse/invoice/create.html"
    model = Invoice
    form_class = InvoiceCreateForm

    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        context["form_errors"] = form.errors
        return self.render_to_response(context)

    def get_success_url(self):
        rental_status = RentalStatus.objects.get(pk=RentalStatus.RENTAL)
        # 貸出中の関連アイテムに請求書を紐づける TODO: どの請求先企業の関連アイテム？の絞りが未対応
        Item.objects.filter(rental_status=rental_status).update(invoice=self.object.id)
        return reverse("war:invoice_detail", kwargs={"pk": self.object.pk})


class InvoiceDetailView(DetailView):
    template_name = "warehouse/invoice/detail.html"
    model = Invoice
    context_object_name = "invoice"


class InvoiceListView(ListView):
    template_name = "warehouse/invoice/list.html"
    model = Invoice

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        mode = self.kwargs.get("mode")
        if mode:
            billing_status = (
                BillingStatus.objects.filter(pk=mode).values("name").first()["name"]
            )
        else:
            billing_status = "すべて"
        context["selected_status"] = billing_status

        return context

    def get_queryset(self, **kwargs):
        mode = self.kwargs.get("mode")
        if mode:
            billing_status = BillingStatus.objects.get(pk=mode)
            invoice = Invoice.objects.filter(billing_status=billing_status)
        else:
            invoice = Invoice.objects.all()

        return invoice
