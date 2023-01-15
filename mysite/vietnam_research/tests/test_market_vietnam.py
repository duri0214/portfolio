from unittest import TestCase

from mysite.vietnam_research.service.market_vietnam import MarketVietnam


class TestMarketVietnam(TestCase):
    def test_calc_fee(self):
        # TODO: なぜかユニットテストで失敗する（modelのimportがエラーを起こしている）
        mkt = MarketVietnam()
        self.assertEqual(1533000, mkt.calc_fee(1500000))  # 1,500,000 VND の手数料は 1,533,000 VND
        self.assertEqual(1200000, mkt.calc_fee(1150000))  # 1,200,000 VNDを下回ったときの手数料は 1,200,000 VND
