from itertools import zip_longest

from jp_stocks.domain.repository.order import OrderRepository
from jp_stocks.domain.valueobject.order import OrderSummary


class OrderBookService:
    """
    売り注文と買い注文をペアにして取り扱うサービスクラス。
    """

    def __init__(self, repository: OrderRepository):
        self.repository = repository

    def get_order_book(
        self,
    ) -> list[tuple[OrderSummary, OrderSummary | None]]:
        """
        売り注文と買い注文をペアにしたリストを取得。
        """
        sell_orders = self.repository.get_sell_orders()
        buy_orders = self.repository.get_buy_orders()

        # 売り注文と買い注文をペアリング
        return list(zip_longest(sell_orders, buy_orders, fillvalue=None))
