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
    price: int
    sell_quantity: int = 0
    buy_quantity: int = 0
