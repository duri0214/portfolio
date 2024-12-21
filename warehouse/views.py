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
                """
                Notes: データベースのポジション値は1から始まりますが、Pythonのリストのインデックスは0から始まります。
                  そのため、データベースのポジション値から1を引くことで、リストの0ベースにしています。
                  これらのポジションをテンプレートでユーザーに表示する際は、1を再度足して1ベースのインデックスに戻します
                """
                shelf_rows[item_position_count["pos_y"] - 1].cells[
                    item_position_count["pos_x"] - 1
                ].item_count += item_position_count["num_items"]

            available_items = Item.objects.filter(
                warehouse_id=warehouse.id, rental_status_id=RentalStatus.STOCK
            )
            non_available_items = Item.objects.filter(
                warehouse_id=warehouse.id
            ).exclude(rental_status_id=RentalStatus.STOCK)

            warehouse_vos.append(
                Warehouse(
                    instance=warehouse,
                    shelves=[
                        Shelf(rows=shelf_rows)
                    ],  # TODO: いまは要素1しかない issue180
                    available_items=available_items,
                    non_available_items=non_available_items,
                )
            )

        context["warehouses"] = warehouse_vos
        context["current_warehouse_id"] = self.request.GET.get("warehouse_id") or (
            warehouse_vos[0].instance.pk if warehouse_vos else None
        )

        return context


class RentItemView(TemplateView):
    template_name = "warehouse/index.html"

    @staticmethod
    def post(request, item_id):
        all_rental_statuses = RentalStatus.objects.in_bulk()

        # rent an item
        item = Item.objects.get(pk=item_id)
        item.rental_status = all_rental_statuses[RentalStatus.RENTAL]
        item.save()

        return redirect(
            reverse("war:index") + "?warehouse_id=" + str(item.warehouse_id)
        )


class ResetRentalsView(TemplateView):
    template_name = "warehouse/index.html"

    @staticmethod
    def post(request, warehouse_id):
        all_rental_statuses = RentalStatus.objects.in_bulk()
        rental_status_stock = all_rental_statuses[RentalStatus.STOCK]
        rental_status_rental = all_rental_statuses[RentalStatus.RENTAL]

        # reset all rentals
        items = Item.objects.filter(
            warehouse_id=warehouse_id, rental_status=rental_status_rental
        )
        items.update(rental_status=rental_status_stock)

        return redirect(reverse("war:index") + "?warehouse_id=" + str(warehouse_id))


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
