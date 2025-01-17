from django.db.models import Sum, F

from jp_stocks.domain.valueobject.order import OrderSummary
from jp_stocks.models import Order


class OrderRepository:
    """
    Orderモデルに対するデータ操作を抽象化するリポジトリクラス。
    データベース操作を行い、注文(order)情報を取得・加工します。
    """

    @staticmethod
    def get_sell_orders() -> list[OrderSummary]:
        """
        売り注文を取得して集計するメソッド。

        各注文に対し、価格(price)ごとに以下の処理を行います:
        - 残量を「quantity - fulfilled_quantity」で計算
        - 残量が0を超えるものだけを対象に集計
        - 残量を合計し、価格(price)ごとに結果をグループ化

        Returns:
            list[OrderSummary]: 売り注文の価格ごとの集計結果（残量含む）
        """
        query = (
            Order.objects.filter(side="sell", status="open")
            .annotate(remaining_quantity=F("quantity") - F("fulfilled_quantity"))
            .filter(remaining_quantity__gt=0)
            .values("price", "status")
            .annotate(total_quantity=Sum("remaining_quantity"))
            .filter(total_quantity__gt=0)
            .order_by("price")
        )
        return [
            OrderSummary(
                price=item["price"],
                total_quantity=item["total_quantity"],
                status=item["status"],
            )
            for item in query
        ]

    @staticmethod
    def get_buy_orders() -> list[OrderSummary]:
        """
        買い注文を取得して集計するメソッド。

        各注文に対し、価格(price)ごとに以下の処理を行います:
        - 残量を「quantity - fulfilled_quantity」で計算
        - 残量が0を超えるものだけを対象に集計
        - 残量を合計し、価格(price)ごとに結果をグループ化

        Returns:
            list[OrderSummary]: 買い注文の価格ごとの集計結果（残量含む）
        """
        query = (
            Order.objects.filter(side="buy", status="open")
            .annotate(remaining_quantity=F("quantity") - F("fulfilled_quantity"))
            .filter(remaining_quantity__gt=0)
            .values("price", "status")
            .annotate(total_quantity=Sum("remaining_quantity"))
            .order_by("-price")
        )
        return [
            OrderSummary(
                price=item["price"],
                total_quantity=item["total_quantity"],
                status=item["status"],
            )
            for item in query
        ]

    @staticmethod
    def get_opposite_orders(side, price, status):
        """
        指定された注文方向に対する反対方向の注文を取得します。

        Args:
            side (str): 現在の注文方向（'buy' または 'sell'）。
            price (Decimal): フィルタ条件となる基準価格。
            status (str): 注文の状態（例: 'open'）。

        Returns:
            QuerySet: フィルタされた反対方向の注文のクエリセット。
        """
        opposite_side = "sell" if side == "buy" else "buy"
        if side == "buy":
            return Order.objects.filter(
                side=opposite_side, price__lte=price, status=status
            ).order_by("price")
        else:
            return Order.objects.filter(
                side=opposite_side, price__gte=price, status=status
            ).order_by("-price")
