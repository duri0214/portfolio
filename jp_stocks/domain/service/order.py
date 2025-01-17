from itertools import zip_longest

from jp_stocks.domain.repository.order import OrderRepository
from jp_stocks.domain.valueobject.order import OrderPair


class OrderBookService:
    """
    売り注文と買い注文をペアにして取り扱うサービスクラス。
    """

    def __init__(self, repository: OrderRepository):
        self.repository = repository

    def get_order_book(
        self,
    ) -> list[OrderPair]:
        """
        売り注文と買い注文のペアリング済みリストを取得する。

        売り注文（SellOrderSummary）と買い注文（BuyOrderSummary）を金額ごとにペアリングする。
        ペアリングの際に、どちらか片方の注文が存在しない場合、その位置は None となる。

        Returns:
            List[OrderPair]: 売り注文と買い注文をペアリングした結果のリスト。
        """
        sell_orders = self.repository.get_sell_orders()
        buy_orders = self.repository.get_buy_orders()

        # 売り注文（左）と買い注文（右）をペアリング
        return [
            OrderPair(sell_order=sell, buy_order=buy)
            for sell, buy in zip_longest(sell_orders, buy_orders, fillvalue=None)
        ]
