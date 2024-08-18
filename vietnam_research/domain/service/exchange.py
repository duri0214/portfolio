from vietnam_research.domain.valueobject.exchange import Currency
from vietnam_research.models import ExchangeRate


class ExchangeService:
    @classmethod
    def get_exchange_rate(cls, base_cur: str, dest_cur: str) -> float:
        # Step1: 通貨ペア（例: JPY/VND）のレートを出すために、USDに換算
        try:
            base_cur_to_usd = ExchangeRate.objects.get(
                base_cur_code=base_cur, dest_cur_code="USD"
            )
            dest_cur_to_usd = ExchangeRate.objects.get(
                base_cur_code=dest_cur, dest_cur_code="USD"
            )
        except ExchangeRate.DoesNotExist:
            raise ValueError(f"レートが見つかりません： {base_cur} or {dest_cur}/USD")

        # USD同士で書式どおり（例: JPY/VND）に割るとレートが出る
        return base_cur_to_usd.rate / dest_cur_to_usd.rate

    @staticmethod
    def calc_purchase_units(budget: Currency, a_unit_price: Currency) -> float:
        """
        予算でいくつ変えるのかを計算します

        予算: 100000円
        rate: 110円/1ドル
        単価: 124.58 USD（NVIDIA）

        予算をUSDに換算: 100000JPY / rate 110USD = 909.09USD
        909.09USDが予算なのでNVIDIAの価格、124.58 USDで割ります

        Args:
            budget: The amount of budget in the currency specified by its code.
            a_unit_price: The unit price of the item in the currency specified by its code.
        """
        # Get exchange rates
        rate_budget = (
            1
            if budget.code == "USD"
            else ExchangeService.get_exchange_rate(base_cur=budget.code, dest_cur="USD")
        )
        rate_unit_price = (
            1
            if a_unit_price.code == "USD"
            else ExchangeService.get_exchange_rate(
                base_cur=a_unit_price.code, dest_cur="USD"
            )
        )

        # Convert budget and unit price to USD
        budget_usd = budget.amount / rate_budget
        unit_price_usd = a_unit_price.amount / rate_unit_price

        rate = ExchangeService.get_exchange_rate(
            base_cur=budget.code, dest_cur=a_unit_price.code
        )
        print(f"為替レート {budget.code}/{a_unit_price.code}: {rate}")

        # Calculate the number of units
        num_units = budget_usd / unit_price_usd
        formatted_num_units = round(num_units, 2)

        formatted_budget = f"{budget.amount}{budget.code}"
        message = f"{formatted_num_units} units = {formatted_budget}→{round(budget_usd, 2)} USD / @{unit_price_usd} USD"
        print(message)

        return formatted_num_units
