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
    def get_opposite_orders(side: str, price: int):
        """
        指定した `side` と `price` に合致する反対方向の注文を取得。

        Arguments:
            side (str): 注文の種類 ("buy" または "sell")
            price (int): 現在の注文の価格

        Returns:
            QuerySet: 条件に一致する注文一覧
        """
        if side == "buy":
            # `買い` の場合は価格が `現在の価格以下` の売り注文を取得
            return Order.objects.filter(side="sell", price__lte=price).order_by(
                "price", "created_at"
            )
        elif side == "sell":
            # `売り` の場合は価格が `現在の価格以上` の買い注文を取得
            return Order.objects.filter(side="buy", price__gte=price).order_by(
                "-price", "created_at"
            )
        return Order.objects.none()  # 条件外の場合（不正値）は空のクエリセットを返す
