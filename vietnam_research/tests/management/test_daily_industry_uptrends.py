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
        expected = 1.05
        self.assertEqual(calc_price(data)["delta"], expected)

    def test_formatted_text_has_value(self):
        code = "AAA"
        slopes = [-0.123, 0.25, -0.1]
        passed = 1
        price = {"initial": 100, "latest": 150, "delta": 50}
        expected = (
            f"{code}｜{slopes}, passed: {passed}, initial: {price.get('initial')},"
            f" latest: {price.get('latest')}, delta: {price.get('delta')}"
        )
        self.assertEqual(formatted_text(code, slopes, passed, price), expected)

    def test_formatted_text_has_no_value(self):
        code = "AAA"
        slopes = [-0.123, 0.25, -0.1]
        passed = 1
        price = {}
        expected = (
            f"{code}｜{slopes}, passed: {passed}, initial: -, latest: -, delta: -"
        )
        self.assertEqual(formatted_text(code, slopes, passed, price), expected)
