from dataclasses import dataclass, field

from vietnam_research.domain.service.market import VietnamMarketDataProvider


@dataclass
class ExchangeProcess:
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
