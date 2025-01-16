from dataclasses import dataclass


@dataclass
class OrderSummary:
    """
    単一の気配値に対応する注文情報を表すValue Object。
    """

    price: float
    total_quantity: int
