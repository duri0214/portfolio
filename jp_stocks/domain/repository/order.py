from typing import List

from django.db.models import Sum

from jp_stocks.domain.valueobject.order import OrderSummary
from jp_stocks.models import Order


class OrderRepository:
    """
    Orderモデルに対するデータ操作を抽象化したリポジトリ。
    """

    @staticmethod
    def get_sell_orders() -> List[OrderSummary]:
        """
        売り注文を気配値ごとに集計して取得。
        """
        query = (
            Order.objects.filter(side="sell", status="open")
            .values("price")
            .annotate(total_quantity=Sum("quantity"))
            .order_by("price")
        )
        return [
            OrderSummary(price=item["price"], total_quantity=item["total_quantity"])
            for item in query
        ]

    @staticmethod
    def get_buy_orders() -> List[OrderSummary]:
        """
        買い注文を気配値ごとに集計して取得。
        """
        query = (
            Order.objects.filter(side="buy", status="open")
            .values("price")
            .annotate(total_quantity=Sum("quantity"))
            .order_by("-price")
        )
        return [
            OrderSummary(price=item["price"], total_quantity=item["total_quantity"])
            for item in query
        ]
