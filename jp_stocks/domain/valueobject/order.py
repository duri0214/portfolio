from dataclasses import dataclass


@dataclass
class OrderSummary:
    """
    注文のサマリーを保持する値オブジェクト。
    Price と Total Quantity のみを保持。
    """

    price: float
    total_quantity: int


@dataclass
class OrderPair:
    """
    売り注文と買い注文のペアリングを表す値オブジェクト。
    """

    sell_order: OrderSummary | None
    buy_order: OrderSummary | None
