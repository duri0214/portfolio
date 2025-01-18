from django.db.models import Sum

from jp_stocks.models import Order


class OrderRepository:
    """
    Order に対するデータ操作を提供するリポジトリクラス。
    """

    @staticmethod
    def get_sell_orders_grouped():
        """
        売り注文を価格帯ごとに集計して取得 (昇順にソート)
        """
        return (
            Order.objects.filter(side="sell")
            .values("price")
            .annotate(total_quantity=Sum("quantity"))
            .order_by("price")
        )

    @staticmethod
    def get_buy_orders_grouped():
        """
        買い注文を価格帯ごとに集計して取得 (降順にソート)
        """
        return (
            Order.objects.filter(side="buy")
            .values("price")
            .annotate(total_quantity=Sum("quantity"))
            .order_by("price")
        )

    @staticmethod
    def get_all_orders():
        """
        全ての注文を取得するが、出力結果はidとside(type)を除外する
        """
        return Order.objects.values("side", "price", "quantity").order_by(
            "price", "-side"
        )
