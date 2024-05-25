from django.test import TestCase

from vietnam_research.service.market_vietnam import MarketVietnam


class TestMarketVietnam(TestCase):
    """
    Notes: PyCharmのunittest経由だと失敗します（Requested setting INSTALLED_APPS ...）
    `python manage.py test vietnam_research` でテストできます
    """

    def test_calc_fee(self):
        mkt = MarketVietnam()
        self.assertEqual(1210000, mkt.calc_fee(55000000))  # 55,000,000 VND の手数料は 1,210,000 VND
        self.assertEqual(1200000, mkt.calc_fee(50000000))  # 手数料が 1,200,000 VNDを下回ったときの手数料は 1,200,000 VND
