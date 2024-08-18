from dataclasses import dataclass, field

from vietnam_research.domain.dataprovider.market import VietnamMarketDataProvider


@dataclass
class ExchangeProcess:
    """
    VNMにおいて 残高 - ((単価 * 口数) + 手数料) を算出する過程

    Attributes:
        current_balance (float): 現在の残高
        unit_price (float): ある株の単価
        quantity (int): ある株を買う口数
        price_no_fee (float): 単価 * 口数
        fee (float): 手数料
        price_in_fee (float): (単価 * 口数) + 手数料
        deduction_price (float): 残高 - ((単価 * 口数) + 手数料)

    Methods:
        __post_init__(): Calculates the price without fee, transaction fee, price with fee, and deducted price.

    Example Usage:
        exchange = ExchangeProcess(current_balance=1000.0, unit_price=10.0, quantity=100)
        print(exchange.price_no_fee)  # Output: 1000.0
        print(exchange.fee)  # Output: 1.0
        print(exchange.price_in_fee)  # Output: 1001.0
        print(exchange.deduction_price)  # Output: -1.0
    """

    current_balance: float
    unit_price: float
    quantity: int
    price_no_fee: float = field(init=False)
    fee: float = field(init=False)
    price_in_fee: float = field(init=False)
    deduction_price: float = field(init=False)

    def __post_init__(self):
        self.price_no_fee = self.unit_price * self.quantity
        self.fee = VietnamMarketDataProvider.calculate_transaction_fee(
            price_without_fees=self.price_no_fee
        )
        self.price_in_fee = self.price_no_fee + self.fee
        self.deduction_price = self.current_balance - self.price_in_fee


@dataclass(frozen=True)
class Currency:
    """
    通貨コードと金額を含む、特定の通貨

    Attributes:
        code (str): 通貨コード
        amount (float): 金額
    """

    code: str
    amount: float
