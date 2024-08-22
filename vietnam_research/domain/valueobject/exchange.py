from dataclasses import dataclass


class ExchangeProcess:
    """
    VNMにおいて ((単価 * 口数) + 手数料) を算出する過程

    Attributes:
    - budget_jpy (float): 予算（円）
    - unit_price (float): ある株の単価
    - rate (float): 為替レート
    - price_no_fee (float): 単価 * 口数
    - fee (float): 手数料
    - price_in_fee (float): (単価 * 口数) + 手数料
    """

    def __init__(
        self,
        budget_jpy: float,
        unit_price: float,
        rate: float,
        purchasable_units: float,
        fee: float,
    ):
        self.budget_jpy = budget_jpy
        self.rate = rate
        self.budget_in_target_currency = budget_jpy * rate
        self.unit_price = unit_price
        self.purchasable_units = purchasable_units
        self.price_no_fee = unit_price * purchasable_units
        self.fee = fee
        self.price_in_fee = self.price_no_fee + self.fee


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


@dataclass(frozen=True)
class UrlScale:
    """
    URL and scale

    Attributes:
        url (str): scraping URL
        scale (int): the scale e.g. x100
    """

    url: str
    scale: int
