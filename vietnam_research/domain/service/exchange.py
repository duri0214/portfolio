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
    def calc_purchase_units(budget: Currency, a_unit_price: Currency):
        # JPY-USDの最新のレートを取得: 1ドルが100円のとき、0.01
        print(
            f"{budget.code=} - {a_unit_price.code=}",
        )
        rate = ExchangeService.get_exchange_rate(
            base_cur=budget.code, dest_cur=a_unit_price.code
        )
        print(f"為替レート (1{budget.code} = {rate} {a_unit_price.code}): {rate}")

        # 予算をドルに換算し、それを単価で割って口数を求める
        budget_usd = budget.amount * rate
        num_stocks = budget_usd / a_unit_price.amount

        print(f"予算（{budget.amount}円）で購入できる口数は約 {num_stocks} 口です。")
