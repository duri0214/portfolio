from django.urls import reverse_lazy
from django.views.generic import TemplateView, CreateView, ListView

from jp_stocks.domain.repository.order import OrderRepository
from jp_stocks.domain.service.order import OrderBookService
from jp_stocks.models import Order


class IndexView(TemplateView):
    template_name = "jp_stocks/index.html"


class OrderBookListView(ListView):
    model = Order
    template_name = "jp_stocks/order_book/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["source_orders"] = OrderRepository.get_all_orders()
        context["combined_orders"] = OrderBookService.calculate_order_book()
        return context


class CreateOrderView(CreateView):
    model = Order
    fields = ["side", "price", "quantity"]
    template_name = "jp_stocks/order_book/create.html"
    success_url = reverse_lazy("jpn:order_book")

    def form_valid(self, form):
        new_order = form.save(commit=True)
        print(f"[INFO] New order created: {new_order}")
        return super().form_valid(form)
