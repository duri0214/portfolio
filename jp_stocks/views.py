from django.urls import reverse_lazy
from django.views.generic import TemplateView, CreateView, ListView

from jp_stocks.models import Order


class IndexView(TemplateView):
    template_name = "jp_stocks/index.html"


class OrderBookListView(ListView):
    model = Order
    template_name = "jp_stocks/order_book/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        sell_orders = Order.objects.filter(side="sell", status="open").order_by("price")
        buy_orders = Order.objects.filter(side="buy", status="open").order_by("-price")

        context["sell_orders"] = sell_orders
        context["buy_orders"] = buy_orders
        return context


class CreateOrderView(CreateView):
    model = Order
    fields = ["side", "price", "quantity"]
    template_name = "jp_stocks/order_book/create.html"
    success_url = reverse_lazy("jpn:index")

    def form_valid(self, form):
        order = form.save(commit=False)
        order.user = self.request.user  # ログインユーザーの取得
        self.match_order(order)  # マッチングロジックの呼び出し
        return super().form_valid(form)

    @staticmethod
    def match_order(new_order):
        # 既存注文をチェック
        opposite_side = "sell" if new_order.side == "buy" else "buy"
        orders = Order.objects.filter(
            side=opposite_side,
            price__lte=(
                new_order.price if new_order.side == "buy" else new_order.price__gte
            ),
            status="open",
        ).order_by("price" if new_order.side == "buy" else "-price")

        for order in orders:
            if new_order.remaining_quantity <= 0:
                break
            trade_quantity = min(order.remaining_quantity, new_order.remaining_quantity)
            order.fulfilled_quantity += trade_quantity
            new_order.fulfilled_quantity += trade_quantity

            # 状態更新
            if order.remaining_quantity == 0:
                order.status = "fulfilled"
            if new_order.remaining_quantity == 0:
                new_order.status = "fulfilled"

            order.save()
        new_order.save()
