from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.views.generic import TemplateView, CreateView, DetailView, ListView

from rental_shop.domain.repository.warehouse import WarehouseRepository
from rental_shop.forms import ItemCreateForm, InvoiceCreateForm
from rental_shop.models import (
    Item,
    RentalStatus,
    Invoice,
    UserAttribute,
    BillingStatus,
    BillingPerson,
    Cart,
    CartItem,
)


class IndexView(TemplateView):
    template_name = "rental_shop/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # ログインしている場合はそのユーザのプロファイルを、そうでない場合はID 1を優先的に取得
        staff = (
            getattr(self.request.user, "rental_profile", None)
            or UserAttribute.objects.first()
        )

        warehouse_vos = WarehouseRepository.find_by_staff(staff)

        context["warehouses"] = warehouse_vos
        context["current_warehouse"] = self.request.GET.get("warehouse_id") or (
            warehouse_vos[0].instance if warehouse_vos else None
        )

        return context


class RentItemView(TemplateView):
    template_name = "rental_shop/index.html"

    @staticmethod
    def post(request, item_id):
        # アイテムを貸し出す（カートに追加）
        item = Item.objects.get(pk=item_id)

        # スタッフと倉庫に対応するカートを取得または作成
        # IndexViewと同様、ログインユーザを優先
        staff = (
            getattr(request.user, "rental_profile", None)
            or UserAttribute.objects.first()
        )
        cart, created = Cart.objects.get_or_create(
            staff=staff, warehouse=item.warehouse
        )

        # カートにまだ存在しない場合は CartItem に追加
        CartItem.objects.get_or_create(cart=cart, item=item)

        # アイテムのステータスを「カート内」に更新
        items = [item]
        for item in items:
            item.rental_status_id = RentalStatus.CART
        Item.objects.bulk_update(items, ["rental_status"])

        return redirect(
            reverse("ren:index") + "?warehouse_id=" + str(item.warehouse_id)
        )


class ResetRentalsView(TemplateView):
    template_name = "rental_shop/index.html"

    @staticmethod
    def post(request, warehouse_id):
        # すべての貸出中アイテムとカート内のアイテムを在庫に戻し、請求書との紐付けを解除
        items = list(
            Item.objects.filter(
                warehouse_id=warehouse_id,
                rental_status_id__in=[RentalStatus.RENTAL, RentalStatus.CART],
            )
        )
        for item in items:
            item.rental_status_id = RentalStatus.STOCK
            item.invoice = None
        Item.objects.bulk_update(items, ["rental_status", "invoice"])

        # この倉庫のカート内アイテムをクリア
        CartItem.objects.filter(item__warehouse_id=warehouse_id).delete()

        return redirect(reverse("ren:index") + "?warehouse_id=" + str(warehouse_id))


class ItemDetailView(DetailView):
    template_name = "rental_shop/item/detail.html"
    model = Item


class ItemCreateView(CreateView):
    template_name = "rental_shop/item/create.html"
    model = Item
    form_class = ItemCreateForm

    def get_initial(self):
        initial = super().get_initial()
        staff = (
            getattr(self.request.user, "rental_profile", None)
            or UserAttribute.objects.first()
        )
        if staff:
            initial["staff"] = staff
        return initial

    def form_valid(self, form):
        form = form.save(commit=False)
        items = [form]
        for item in items:
            item.rental_status_id = RentalStatus.STOCK
        # 新規作成時は save() が必要だが、一貫性のためにリスト化して扱う（新規は bulk_update 不可なので最終的に save）
        item = items[0]
        item.save()
        return redirect("ren:item_create")

    def form_invalid(self, form):
        messages.add_message(self.request, messages.WARNING, form.errors.as_text())
        return super().form_invalid(form)


class InvoiceCreateView(CreateView):
    template_name = "rental_shop/invoice/create.html"
    model = Invoice
    form_class = InvoiceCreateForm

    def get_initial(self):
        initial = super().get_initial()
        staff = (
            getattr(self.request.user, "rental_profile", None)
            or UserAttribute.objects.first()
        )
        if staff:
            initial["staff"] = staff
        return initial

    def form_invalid(self, form):
        context = self.get_context_data(form=form)
        context["form_errors"] = form.errors
        return self.render_to_response(context)

    def get_success_url(self):
        # このスタッフのカート内のアイテムを確定させる（貸出中に変更し、請求書を紐付ける）
        items = list(Item.objects.filter(cartitem__cart__staff=self.object.staff))
        for item in items:
            item.rental_status_id = RentalStatus.RENTAL
            item.invoice = self.object
        Item.objects.bulk_update(items, ["rental_status", "invoice"])

        # このスタッフのカート内アイテム（関連）をクリア
        CartItem.objects.filter(cart__staff=self.object.staff).delete()

        return reverse("ren:invoice_detail", kwargs={"pk": self.object.pk})


class InvoiceDetailView(DetailView):
    template_name = "rental_shop/invoice/detail.html"
    model = Invoice
    context_object_name = "invoice"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["items"] = Item.objects.filter(invoice=self.object)
        return context


class InvoiceListView(ListView):
    template_name = "rental_shop/invoice/list.html"
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


def load_billing_persons(request):
    """会社に紐づく請求担当者をJSON形式で返すAjaxエンドポイント"""
    company_id = request.GET.get("company_id")
    billing_persons = BillingPerson.objects.filter(company_id=company_id).order_by(
        "name"
    )
    return JsonResponse(list(billing_persons.values("id", "name")), safe=False)
