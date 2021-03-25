"""views.py"""
import os
import io
import csv
import json
from django.conf import settings
from django.shortcuts import redirect, render
from django.http.response import JsonResponse
from django.views.generic import TemplateView, DetailView, CreateView, FormView
from django.contrib import messages
from django.urls import reverse_lazy
import stripe
from .models import Products, BuyingHistory
from .forms import EditForm, RegisterFormSingle, RegisterFormBulk

# read APIKEY
with open(settings.BASE_DIR + '/shopping/api_setting/apikey.txt', mode='r') as file:
    stripe.api_key = file.read()


class UploadSingleView(CreateView):
    """UploadSingleView"""
    model = Products
    template_name = "shopping/product/register_single.html"
    form_class = RegisterFormSingle
    success_url = reverse_lazy('shp:index')

    def form_valid(self, form):
        # prepare
        code = form.cleaned_data.get('code')
        # delete if old exists for db
        Products.objects.filter(code=code).delete()
        form.save()
        # e.g. filename: apple, ext: .png
        filename, ext = os.path.splitext(form.cleaned_data["picture"].name)
        # delete if old exists for file
        move_to = settings.STATIC_ROOT + '/shopping/img/' + code + ext.lower()
        if os.path.exists(move_to):
            os.remove(move_to)
        # move file from media directory
        move_from = settings.MEDIA_ROOT + '/shopping/' + filename + ext.lower()
        os.rename(move_from, move_to)
        return super().form_valid(form)

    def form_invalid(self, form):
        print(form.errors)
        messages.add_message(self.request, messages.WARNING, form.errors)
        return redirect('shp:index')


class UploadBulkView(FormView):
    """UploadBulkView"""
    template_name = "shopping/product/register_bulk.html"
    form_class = RegisterFormBulk
    success_url = reverse_lazy('shp:index')

    def form_valid(self, form):
        # read csv
        reader = csv.reader(io.TextIOWrapper(form.cleaned_data["file"], encoding='utf-8'))
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
        return redirect('shp:index')


class IndexView(TemplateView):
    """IndexView"""
    template_name = 'shopping/index.html'
    # model = Products
    # paginate_by = 5 # TODO paging

    def post(self, request, *args, **kwargs):
        """post"""
        # mode read
        mode = self.kwargs.get("mode")
        if mode != 0:
            # update
            form = EditForm(request.POST)
            if form.is_valid():
                product = Products.objects.get(code=form.cleaned_data['code'])
                product.code = form.cleaned_data['code']
                product.name = form.cleaned_data['name']
                product.price = form.cleaned_data['price']
                product.description = form.cleaned_data['description']
                product.save()
            return redirect('shp:index')
        # read
        data = json.loads(request.body)
        data = Products.objects.get(code=data.get('code'))
        # response json
        return JsonResponse({
            "code": data.code,
            "name": data.name,
            "price": data.price,
            "description": data.description
        })

    def get_context_data(self, **kwargs):
        # prepare blank form
        context = super().get_context_data(**kwargs)
        context['products'] = Products.objects.all()
        context['editable_list'] = Products.objects.order_by('id')[:5]
        context['editable_form'] = EditForm()
        return context


class ProductDetailView(DetailView):
    """DetailView"""
    template_name = 'shopping/detail.html'
    model = Products

    def post(self, request, *args, **kwargs):
        """post"""
        product = self.get_object()
        token = request.POST['stripeToken']  # 'stripeToken' will made by form submit
        try:
            # buy
            charge = stripe.Charge.create(
                amount=product.price,
                currency='jpy',
                source=token,
                description='メール:{} 商品名:{}'.format(request.user.email, product.name),
            )
        except stripe.error.CardError as errors:
            # errors: Payment was not successful. e.g. payment limit over
            context = self.get_context_data()
            context['message'] = errors.error.message
            return render(request, 'shopping/product_detail.html', context)
        else:
            # ok
            BuyingHistory.objects.create(product=product, user=request.user, stripe_id=charge.id)
            return redirect('shp:index')

    def get_context_data(self, **kwargs):
        """STRIPE_PUBLIC_KEYを渡したいだけ"""
        context = super().get_context_data(**kwargs)
        context['public_key'] = settings.STRIPE_PUBLIC_KEY
        return context
