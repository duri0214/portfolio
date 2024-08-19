from vietnam_research.domain.valueobject.exchange import Currency
from vietnam_research.models import ExchangeRate


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
        else:
            return ExchangeRate.objects.get(
                base_cur_code=base_cur, dest_cur_code=dest_cur
            ).rate

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
