from django.test import TestCase


class TestMarketNasdaq(TestCase):
    def test_calc_fee(self):
        # TODO: sqlalchemyをアンインストールするほうを優先したので、テストはいったんOFF
        # mkt = MarketNasdaq()
        # self.assertEqual(22, mkt.calc_fee(5000))    # $5000 の手数料は $24.75->$22
        # self.assertEqual(2.475, mkt.calc_fee(500))  # $500 の手数料は  $2.475
        pass
