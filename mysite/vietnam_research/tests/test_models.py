import datetime
from unittest import TestCase

from mysite.vietnam_research.models import Industry


class TestIndustry(TestCase):
    def test_slipped_month_end(self):
        # TODO: なぜかユニットテストで失敗する（modelのimportがエラーを起こしている？）
        expected_value = datetime.datetime(2022, 2, 28)
        self.assertEqual(Industry.objects.slipped_month_end(-1, datetime.datetime(2022, 3, 15)), expected_value)
