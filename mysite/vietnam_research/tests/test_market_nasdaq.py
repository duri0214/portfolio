from unittest import TestCase

from mysite.vietnam_research.market_nasdaq import MarketNasdaq


class TestMarketNasdaq(TestCase):
    def test_calc_fee(self):
        mkt = MarketNasdaq()
        self.assertEqual(22, mkt.calc_fee(5000))    # $5000 の手数料は $24.75->$22
        self.assertEqual(2.475, mkt.calc_fee(500))  # $500 の手数料は  $2.475
