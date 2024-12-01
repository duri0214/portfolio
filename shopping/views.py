import csv
import io
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

from .forms import (
    RegisterFormSingle,
    RegisterFormBulk,
    ProductEditForm,
    StaffEditForm,
    StaffDetailForm,
    StaffCreateForm,
)
from .models import Products, BuyingHistory, Staff

# stripe api key
stripe.api_key = os.environ.get("SHOPPING")


class CreateSingle(CreateView):
    model = Products
    template_name = "shopping/product/create_single.html"
    form_class = RegisterFormSingle
    success_url = reverse_lazy("shp:index")

    def form_valid(self, form):
        # prepare
        code = form.cleaned_data.get("code")
        # delete if old exists for db
        Products.objects.filter(code=code).delete()
        form.save()
        # e.g. filename: apple, ext: .png
        filename, ext = os.path.splitext(form.cleaned_data["picture"].name)
        # delete if old exists for file
        move_to = settings.STATIC_ROOT + "/shopping/img/" + code + ext.lower()
        if os.path.exists(move_to):
            os.remove(move_to)
        # move file from media directory
        move_from = settings.MEDIA_ROOT + "/shopping/" + filename + ext.lower()
        os.rename(move_from, move_to)
        return super().form_valid(form)

    def form_invalid(self, form):
        print(form.errors)
        messages.add_message(self.request, messages.WARNING, form.errors)
        return redirect("shp:index")


class CreateBulk(FormView):
    template_name = "shopping/product/create_bulk.html"
    form_class = RegisterFormBulk
    success_url = reverse_lazy("shp:index")

    def form_valid(self, form):
        # read csv
        reader = csv.reader(
            io.TextIOWrapper(form.cleaned_data["file"], encoding="utf-8")
        )
        # ignore header
        next(reader)
        # count of insert
        for record in reader:
            # insert if the record not exists.
            product, created = Products.objects.get_or_create(code=record[0])
            product.code = record[0]
            product.name = record[1]
            product.price = record[2]
            product.description = record[3]
            product.save()
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.add_message(self.request, messages.WARNING, form.errors)
        return redirect("shp:index")


class Index(ListView):
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
