from django.core.exceptions import ObjectDoesNotExist

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

    @staticmethod
    def calc_purchase_units(budget: Currency, unit_price: Currency) -> float:
        """
        予算でいくつ買えるのかを計算します
        budgetを相手側（＝unit_price）通貨に変換してから処理します

        Notes: JPYからUSDへ換算するには、JPY額をJPY/USDのレートで乗じます

        Args:
            budget: 予算
            unit_price: 単価
        """
        # Get exchange rates
        rate = ExchangeService.get_rate(base_cur=budget.code, dest_cur=unit_price.code)

        # Convert budget to unit price currency
        budget_in_dest_cur = budget.amount * rate

        # Calculate the number of units
        try:
            num_units = budget_in_dest_cur / unit_price.amount
        except ZeroDivisionError:
            # If unit_price.amount is 0, return 0
            return 0

        return round(num_units, 2)
