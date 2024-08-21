from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase

from vietnam_research.domain.service.exchange import ExchangeService
from vietnam_research.domain.valueobject.exchange import Currency
from vietnam_research.models import ExchangeRate


class TestExchangeService(TestCase):
    def setUp(self):
        ExchangeRate.objects.create(
            base_cur_code="USD",
            dest_cur_code="JPY",
            rate=110.0,
        )
        ExchangeRate.objects.create(
            base_cur_code="JPY",
            dest_cur_code="VND",
            rate=170.55,
        )

    def test_get_rate(self):
        actual = ExchangeService.get_rate("USD", "JPY")
        expected = 110.0
        self.assertEqual(expected, actual)

    def test_get_rate_inverted(self):
        actual = ExchangeService.get_rate("VND", "JPY")
        expected = 1 / 170.55
        self.assertAlmostEqual(expected, actual)

    def test_get_rate_not_exist(self):
        with self.assertRaises(ObjectDoesNotExist):
            ExchangeService.get_rate("EUR", "JPY")

    def test_calc_purchase_units_usd(self):
        """
        予算: 100000円
        rate: 0.00909
        単価: 124.58 USD (NVIDIA)

        Notes: JPYからUSDへ換算するには、JPY額をJPY/USDのレートで乗じます
        """
        budget = Currency(code="JPY", amount=100000)
        unit_price = Currency(code="USD", amount=124.58)

        actual = ExchangeService().calc_purchase_units(
            budget=budget, unit_price=unit_price
        )
        expected = 7.3  # 100000 * 0.00909 / @124.58

        self.assertAlmostEqual(expected, actual)

    def test_calc_purchase_units_vnd(self):
        """
        予算: 100000円
        rate: 170.55
        単価: 100000 VND

        Notes: JPYからVNDへ換算するには、JPY額をJPY/VNDのレートで乗じます
        """
        budget = Currency(code="JPY", amount=100000)
        unit_price = Currency(code="VND", amount=100000)

        actual = ExchangeService().calc_purchase_units(
            budget=budget, unit_price=unit_price
        )
        expected = 170.55  # 100000 * 170.55 / @100000

        self.assertAlmostEqual(expected, actual)
