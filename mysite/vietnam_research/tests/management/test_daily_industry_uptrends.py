from django.test import TestCase
import pandas as pd

from vietnam_research.management.commands.daily_industry_uptrends import calc_price


class Test(TestCase):
    """
    Notes: PyCharmのunittest経由だと失敗します（Requested setting INSTALLED_APPS ...）
    `python manage.py test --pattern="test_d*.py"` でテストできます
    """
    def test_calc_price(self):
        data = pd.Series([7.17, 7.14, 7.07, 7.07, 7.19, 7.19, 7.12, 7.16, 7.40, 7.58, 7.59, 7.79, 8.33, 8.22])
        expected_value = 1.05
        self.assertEqual(calc_price(data)['delta'], expected_value)
