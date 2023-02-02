from io import StringIO
from django.core.management import call_command
from django.test import TestCase
import pandas as pd

from vietnam_research.management.commands.daily_industry_uptrends import calc_price


class Test(TestCase):
    """
    Notes: PyCharmのunittest経由だと失敗します（Requested setting INSTALLED_APPS ...）
    `python manage.py test --pattern="test_d*.py"` でテストできます
    """
    def test_calc_price(self):
        # TODO: Django式のテストの仕方でやって
        # See Also: https://docs.djangoproject.com/en/4.2/topics/testing/tools/#topics-testing-management-commands
        call_command('daily_industry_uptrends', stdout=StringIO())
        data = pd.Series([7.17, 7.14, 7.07, 7.07, 7.19, 7.19, 7.12, 7.16, 7.40, 7.58, 7.59, 7.79, 8.33, 8.22])
        expected_value = 1.05
        self.assertEqual(calc_price(data)['delta'], expected_value)
