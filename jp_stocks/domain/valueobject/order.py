from dataclasses import dataclass


@dataclass
class OrderPair:
    price: int
    sell_quantity: int = 0
    buy_quantity: int = 0
