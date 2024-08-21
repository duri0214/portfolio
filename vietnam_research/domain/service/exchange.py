from dataclasses import field, dataclass

from django.core.exceptions import ObjectDoesNotExist

from vietnam_research.domain.dataprovider.market import VietnamMarketDataProvider
from vietnam_research.domain.valueobject.exchange import Currency
from vietnam_research.models import ExchangeRate


@dataclass
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

    budget_jpy: float
    unit_price: float
    rate: float = field(init=False)
    purchasable_units: float = field(init=False)
    price_no_fee: float = field(init=False)
    fee: float = field(init=False)
    price_in_fee: float = field(init=False)

    def __post_init__(self):
        self.rate = ExchangeService.get_rate(base_cur="JPY", dest_cur="VND")
        self.purchasable_units = ExchangeService().calc_purchase_units(
            budget=Currency(code="JPY", amount=self.budget_jpy),
            unit_price=Currency(code="VND", amount=self.unit_price),
        )
        self.price_no_fee = self.unit_price * self.purchasable_units
        self.fee = VietnamMarketDataProvider.calculate_transaction_fee(
            price_without_fees=self.price_no_fee
        )
        self.price_in_fee = self.price_no_fee + self.fee


class ExchangeService:
    @staticmethod
    def get_rate(base_cur: str, dest_cur: str) -> float:
        """
        Args:
            base_cur (str): The 自分方 通貨コード
            dest_cur (str): The 相手方 通貨コード

        Returns:
            float: 通貨ペアの為替レート（baseとdestが同じ場合は 1）
        """
        if base_cur == dest_cur:
            return 1
        try:
            # dbからレートを取得
            rate = ExchangeRate.objects.get(
                base_cur_code=base_cur, dest_cur_code=dest_cur
            ).rate
        except ObjectDoesNotExist:
            try:
                # ひっくり返してレートを取得し、その逆数を返す
                rate = (
                    1
                    / ExchangeRate.objects.get(
                        base_cur_code=dest_cur, dest_cur_code=base_cur
                    ).rate
                )
            except ObjectDoesNotExist:
                # 両方が見つからない場合は例外
                raise ObjectDoesNotExist(
                    f"No exchange rate found for currency pair {base_cur}-{dest_cur}"
                )
        return rate

    def calc_purchase_units(self, budget: Currency, unit_price: Currency) -> float:
        """
        予算でいくつ買えるのかを計算します
        budgetを相手側（＝unit_price）通貨に変換してから処理します

        Notes: JPYからUSDへ換算するには、JPY額をJPY/USDのレートで乗じます

        Args:
            budget: 予算
            unit_price: 単価
        """
        # Get exchange rates
        rate = self.get_rate(base_cur=budget.code, dest_cur=unit_price.code)

        # Convert budget to unit price currency
        budget_in_dest_cur = budget.amount * rate

        # Calculate the number of units
        num_units = budget_in_dest_cur / unit_price.amount

        return round(num_units, 2)
