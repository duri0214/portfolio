from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import now

from vietnam_research.forms import WatchlistCreateForm
from vietnam_research.models import Symbol, IndClass, Market, Industry, ExchangeRate


class FormTests(TestCase):
    def setUp(self):
        Symbol.objects.create(
            code="AAA",
            name="アンファット・バイオプラスチック",
            ind_class=IndClass.objects.create(
                industry1="農林水産業", industry2="天然ゴム", industry_class=1
            ),
            market=Market.objects.create(code="HOSE", name="ホーチミン証券取引所"),
        )

        ExchangeRate.objects.create(
            base_cur_code="JPY",
            dest_cur_code="VND",
            rate=170.55,
        )

    def test_watchlist_form_valid(self):
        """test No.1: 正常な入力を行えばエラーにならない"""
        symbol = Symbol.objects.get(code="AAA")
        params = dict(
            symbol=symbol, bought_day=now(), stocks_price=1000, stocks_count=500
        )
        form = WatchlistCreateForm(params, instance=Industry())
        self.assertTrue(form.is_valid())

    def test_watchlist_form_invalid(self):
        """test No.2: 何も入力しなければエラーになることを検証"""
        params = dict()
        form = WatchlistCreateForm(params, instance=Industry())
        self.assertFalse(form.is_valid())

    def test_exchange_calc(self):
        """test No.3: 残高4,029,139VND, 単価50,000, 口数200のときに足りない額は7,290,861"""
        response = self.client.post(reverse('vnm:index'), {
            'current_balance': 4029139,
            'unit_price': 50000,
            'quantity': 200
        }, follow=True)
        self.assertContains(response, '差引残高: -7,170,861 VND')
