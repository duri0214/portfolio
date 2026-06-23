import numpy as np
import pandas as pd
from django.test import TestCase

from vietnam_research.management.commands.daily_industry_chart_and_uptrend import (
    calc_price,
    formatted_text,
)


class Test(TestCase):
    """
    Notes: PyCharmのunittest経由だと失敗します（Requested setting INSTALLED_APPS ...）
    `python manage.py test --pattern="test_d*.py"` でテストできます
    """

    def test_calc_price(self):
        """
        シナリオ:
        - 入力: 14日分の終値データ。
        - 処理: calc_price を呼び出す。
        - 期待値: 初日から最終日までの変化率が小数2桁で返されること。
        """
        data = pd.Series(
            [
                7.17,
                7.14,
                7.07,
                7.07,
                7.19,
                7.19,
                7.12,
                7.16,
                7.40,
                7.58,
                7.59,
                7.79,
                8.33,
                8.22,
            ]
        )
        expected = 14.64
        self.assertEqual(calc_price(data)["delta"], expected)

    def test_formatted_text_has_value(self):
        """
        シナリオ:
        - 入力: numpy由来の傾き、通過数、価格情報。
        - 処理: formatted_text を呼び出す。
        - 期待値: numpyの型表現を含まず、小数2桁に整形された文字列が返されること。
        """
        code = "AAA"
        slopes = [np.float64(-0.123), np.float64(0.25), np.float64(-0.1)]
        passed = 1
        price = {"initial": np.float64(100), "latest": 150, "delta": 50}
        expected = (
            f"{code}｜slopes: [-0.12, 0.25, -0.10], passed: {passed},"
            " initial: 100.00, latest: 150.00, delta: 50.00"
        )
        actual = formatted_text(code, slopes, passed, price)
        self.assertEqual(actual, expected)
        self.assertNotIn("np.float", actual)

    def test_formatted_text_has_no_value(self):
        """
        シナリオ:
        - 入力: 傾きと通過数のみで、価格情報が空の辞書。
        - 処理: formatted_text を呼び出す。
        - 期待値: 価格情報はハイフンで表示され、傾きは小数2桁で返されること。
        """
        code = "AAA"
        slopes = [-0.123, 0.25, -0.1]
        passed = 1
        price = {}
        expected = f"{code}｜slopes: [-0.12, 0.25, -0.10], passed: {passed}, initial: -, latest: -, delta: -"
        self.assertEqual(formatted_text(code, slopes, passed, price), expected)
