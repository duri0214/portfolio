from unittest import TestCase

from mysite.vietnam_research.service.market_vietnam import MarketVietnam


class TestMarketVietnam(TestCase):
    def test_calc_fee(self):
        # TODO: なぜかユニットテストで失敗する（modelのimportがエラーを起こしている）
        mkt = MarketVietnam()
        self.assertEqual(1210000, mkt.calc_fee(55000000))  # 55,000,000 VND の手数料は 1,210,000 VND
        self.assertEqual(1200000, mkt.calc_fee(50000000))  # 手数料が 1,200,000 VNDを下回ったときの手数料は 1,200,000 VND
