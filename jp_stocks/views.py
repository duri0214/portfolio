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
        order_book_service = OrderBookService(repository=OrderRepository())
        context["combined_orders"] = order_book_service.get_order_book()
        return context


class CreateOrderView(CreateView):
    model = Order
    fields = ["side", "price", "quantity"]
    template_name = "jp_stocks/order_book/create.html"
    success_url = reverse_lazy("jpn:order_book")

    def form_valid(self, form):
        order = form.save(commit=False)
        self.match_order(order)
        return super().form_valid(form)

    @staticmethod
    def match_order(new_order):
        orders = OrderRepository.get_opposite_orders(
            side=new_order.side, price=new_order.price, status="open"
        )

        for order in orders:
            # 残量計算を正確に行う
            remaining_new_order_quantity = (
                new_order.quantity - new_order.fulfilled_quantity
            )
            remaining_order_quantity = order.quantity - order.fulfilled_quantity

            if remaining_new_order_quantity <= 0:
                break  # マッチング不要

            # 消化量を計算
            trade_quantity = min(remaining_new_order_quantity, remaining_order_quantity)

            # fulfilled_quantity を更新
            order.fulfilled_quantity += trade_quantity
            new_order.fulfilled_quantity += trade_quantity

            # 状態更新
            if order.fulfilled_quantity == order.quantity:
                order.status = "fulfilled"
            if new_order.fulfilled_quantity == new_order.quantity:
                new_order.status = "fulfilled"

            order.save()
        new_order.save()
