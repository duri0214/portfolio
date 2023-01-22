import datetime
from unittest import TestCase

from vietnam_research.models import Industry


class TestIndustry(TestCase):
    """
    Notes: PyCharmのunittest経由だと失敗します（Requested setting INSTALLED_APPS ...）
    `python manage.py test vietnam_research` でテストできます
    """
    def test_slipped_month_end(self):
        expected_value = datetime.date(2022, 2, 28)
        self.assertEqual(Industry.objects.slipped_month_end(-1, datetime.datetime(2022, 3, 15)).recorded_date, expected_value)
