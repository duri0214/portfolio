from django.test import TestCase

from vietnam_research.domain.service.market import VietnamMarketDataProvider


class TestMarketVietnam(TestCase):
    """
    Notes: PyCharmのunittest経由だと失敗します（Requested setting INSTALLED_APPS ...）
    `python manage.py test vietnam_research` でテストできます
    """

    def test_calc_fee(self):
        # 60,000,000 * 0.022 = 1,320,000 (最低手数料に一致)
        self.assertEqual(
            1320000, VietnamMarketDataProvider.calculate_transaction_fee(60000000)
        )
        # 50,000,000 * 0.022 = 1,100,000 < 1,320,000 (最低手数料が適用される)
        self.assertEqual(
            1320000, VietnamMarketDataProvider.calculate_transaction_fee(50000000)
        )
