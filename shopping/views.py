import os

import stripe
from django.conf import settings
from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views.generic import (
    DetailView,
    CreateView,
    FormView,
    UpdateView,
    ListView,
)

from .domain.service.product import CsvService
from .forms import (
    ProductCreateFormSingle,
    ProductCreateFormBulk,
    ProductEditForm,
    StaffEditForm,
    StaffDetailForm,
    StaffCreateForm,
)
from .models import Products, BuyingHistory, Staff

# stripe api key
stripe.api_key = os.environ.get("STRIPE_API_KEY")


class CreateSingle(CreateView):
    model = Products
    template_name = "shopping/product/create_single.html"
    form_class = ProductCreateFormSingle
    success_url = reverse_lazy("shp:index")

    def form_valid(self, form):
        try:
            self.object = form.save()
            return super().form_valid(form)
        except Exception as e:
            print(f"商品作成中にエラーが発生: {e}")
            form.add_error(None, f"商品の作成に失敗しました: {e}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        print(form.errors)
        messages.add_message(self.request, messages.WARNING, form.errors)
        return redirect("shp:index")


class CreateBulk(FormView):
    template_name = "shopping/product/create_bulk.html"
    form_class = ProductCreateFormBulk
    success_url = reverse_lazy("shp:index")

    def form_valid(self, form):
        try:
            # CSVファイルをサービスに渡して処理
            csv_file = form.cleaned_data["file"]
            results = CsvService.process(csv_file)

            # 処理結果をメッセージとして表示
            if results["success_count"] > 0:
                messages.success(
                    self.request,
                    f"{results['success_count']}件の商品を正常に処理しました。",
                )

            if results["error_count"] > 0:
                messages.warning(
                    self.request,
                    f"{results['error_count']}件の商品で処理エラーが発生しました。",
                )
                for error in results["errors"][:5]:  # 最初の5つのエラーのみ表示
                    messages.error(self.request, error)
                if len(results["errors"]) > 5:
                    messages.error(
                        self.request,
                        f"他にも{len(results['errors']) - 5}件のエラーが発生しています。",
                    )

            return super().form_valid(form)

        except Exception as e:
            form.add_error(None, f"商品の一括作成に失敗しました: {str(e)}")
            return self.form_invalid(form)

    def form_invalid(self, form):
        messages.error(self.request, "フォームの入力に問題があります")
        return super().form_invalid(form)


class IndexView(ListView):
    model = Products
    template_name = "shopping/index.html"
    paginate_by = 5

    def get_queryset(self):
        return Products.objects.order_by("id")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["staffs"] = Staff.objects.all()
        return context


class ProductDetail(DetailView):
    """DetailView"""

    template_name = "shopping/product/detail.html"
    model = Products

    def post(self, request, *args, **kwargs):
        """post"""
        product = self.get_object()
        token = request.POST["stripeToken"]  # 'stripeToken' will be made by form submit
        try:
            # buy
            charge = stripe.Charge.create(
                amount=product.price,
                currency="jpy",
                source=token,
                description="メール:{} 商品名:{}".format(
                    request.user.email, product.name
                ),
            )
        except stripe.error.CardError as errors:
            # errors: Payment was not successful. e.g. payment limit over
            context = self.get_context_data()
            context["message"] = errors.error.message
            return render(request, "shopping/product/detail.html", context)
        else:
            # ok
            BuyingHistory.objects.create(
                product=product, user=request.user, stripe_id=charge.id
            )
            return redirect("shp:index")

    def get_context_data(self, **kwargs):
        """STRIPE_PUBLIC_KEYを渡したいだけ"""
        context = super().get_context_data(**kwargs)
        context["public_key"] = settings.STRIPE_PUBLIC_KEY
        return context


class ProductEdit(UpdateView):
    template_name = "shopping/product/edit.html"
    form_class = ProductEditForm
    success_url = reverse_lazy("shp:index")
    model = Products


class StaffDetail(DetailView):
    template_name = "shopping/staff/detail.html"
    form_class = StaffDetailForm
    model = Staff


class StaffEdit(UpdateView):
    template_name = "shopping/staff/edit.html"
    form_class = StaffEditForm
    success_url = reverse_lazy("shp:index")
    model = Staff


class StaffCreate(CreateView):
    template_name = "shopping/staff/create.html"
    form_class = StaffCreateForm
    success_url = reverse_lazy("shp:index")
    model = Staff
