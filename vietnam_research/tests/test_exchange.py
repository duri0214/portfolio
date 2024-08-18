from django.test import TestCase

from vietnam_research.domain.service.exchange import ExchangeService
from vietnam_research.domain.valueobject.exchange import Currency
from vietnam_research.models import ExchangeRate


class TestExchangeService(TestCase):
    def setUp(self):
        self.base_cur = "USD"
        self.dest_cur = "JPY"
        self.rate_base = 1.0
        self.rate_dest = 110.0

        ExchangeRate.objects.create(
            base_cur_code=self.base_cur, dest_cur_code="USD", rate=self.rate_base
        )
        ExchangeRate.objects.create(
            base_cur_code=self.dest_cur, dest_cur_code="USD", rate=self.rate_dest
        )

    def test_get_exchange_rate(self):
        rate = ExchangeService.get_exchange_rate(self.base_cur, self.dest_cur)
        self.assertEqual(rate, self.rate_base / self.rate_dest)

    def test_get_exchange_rate_not_exist(self):
        with self.assertRaises(ValueError):
            ExchangeService.get_exchange_rate("EUR", "JPY")

    def test_calc_purchase_units(self):
        budget = Currency(code="JPY", amount=100000)
        a_unit_price = Currency(code="USD", amount=124.58)

        result = ExchangeService.calc_purchase_units(budget, a_unit_price)
        expected = round((100000 / 110) / 124.58, 2)

        self.assertAlmostEqual(expected, result)
