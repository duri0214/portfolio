from django.http import HttpRequest
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import resolve
from django.utils.timezone import now

from .forms import WatchlistForm
from .market_nasdaq import MarketNasdaq
from .market_vietnam import MarketVietnam
from .models import Industry
from .views import index


class TestAbstract(TestCase):
    """ test No.1: vietnam market 用のクラスをテストします"""
    def test_market_vietnam(self):
        v = MarketVietnam()
        self.assertEqual('mysql+mysqldb://python:python123@127.0.0.1/pythondb?charset=utf8&use_unicode=1', v._con_str)


class IndustryModelTests(TestCase):
    def test_is_empty(self):
        """ test No.1: テーブルは0件です"""
        saved_industry = Industry.objects.all()
        self.assertEqual(saved_industry.count(), 0)

    def test_is_not_empty(self):
        """test No.2: 1つ登録すれば保存されたレコード数は1"""
        industry = Industry()
        industry.pub_date = now()
        industry.save()
        saved_industries = Industry.objects.all()
        self.assertEqual(saved_industries.count(), 1)

    def test_saving_and_get_industry(self):
        """test No.3: 入れる前のデータと入れたあとのデータは等しい"""
        first_industry = Industry()
        market_code, symbol, company_name = "HOSE", "AAA", "アンファット・バイオプラスチック"
        first_industry.market_code = market_code
        first_industry.symbol = symbol
        first_industry.company_name = company_name
        first_industry.pub_date = now()
        first_industry.save()
        saved_industries = Industry.objects.all()
        actual_industry = saved_industries[0]
        self.assertEqual(actual_industry.market_code, market_code)
        self.assertEqual(actual_industry.symbol, symbol)
        self.assertEqual(actual_industry.company_name, company_name)


class UrlResolveTests(TestCase):
    def test_url_resolves_to_book_list_view(self):
        """test No.1: /では、indexが呼び出される事を検証"""
        found = resolve('/')
        self.assertEqual(found.func, index)


# class HtmlTests(TestCase):
#     def test_book_list_page_returns_correct_html(self):
#         """test No.1: /では、HTMLを検証"""
#         request = HttpRequest()
#         response = index(request)
#         expected_html = render_to_string('/')
#         self.assertEqual(response.content.decode(), expected_html)


class FormTests(TestCase):
    def test_valid(self):
        """test No.1: 正常な入力を行えばエラーにならない"""
        params = dict(symbol='HOSE', bought_day=now(), stocks_price=1000, stocks_count=500)
        industry = Industry()
        form = WatchlistForm(params, instance=industry)
        self.assertTrue(form.is_valid())

    def test_either1(self):
        """test No.2: 何も入力しなければエラーになることを検証"""
        params = dict()
        industry = Industry()
        form = WatchlistForm(params, instance=industry)
        self.assertFalse(form.is_valid())

    def test_exchange_calc(self):
        """test No.3: 残高4,029,139VND, 単価50,000, 口数200のときに足りない額は7,290,861"""
        update_url = '/'
        # GET the form
        r = self.client.get(update_url)
        # retrieve form data as dict
        form = r.context['exchange_form']
        # manipulate some data
        data = form.initial  # form is unbound but contains data
        data['current_balance'] = 4029139
        data['unit_price'] = 50000
        data['quantity'] = 200
        # POST to the form
        r = self.client.post(update_url, data)
        self.assertContains(r, 'q=-7290861vnd')

    def test_fee_vietnam(self):
        """test No.4: 最低手数料を返すパターンと、通常手数料を返すパターン"""
        mkt = MarketVietnam()
        self.assertEqual(1320000, mkt.calc_fee(1000000))    # 1000000VNDの手数料は   22000VND->1320000VND
        self.assertEqual(2200000, mkt.calc_fee(100000000))  # 100000000VNDの手数料は 2200000VND

    def test_fee_usa(self):
        """test No.5: 最大手数料を返すパターンと、通常手数料を返すパターン"""
        mkt = MarketNasdaq()
        self.assertEqual(22, mkt.calc_fee(5000))    # $5000 の手数料は $24.75->$22
        self.assertEqual(2.475, mkt.calc_fee(500))  # $500 の手数料は  $2.475


class CanSaveAPostRequestAssert(TestCase):
    def assertFieldInResponse(self, response, name, page, publisher):
        self.assertIn(name, response.content.decode())
        self.assertIn(page, response.content.decode())
        self.assertIn(publisher, response.content.decode())


class CanSaveAPostRequestTests(CanSaveAPostRequestAssert):
    def post_request(self, name, page, publisher):
        request = HttpRequest()
        request.method = 'POST'
        request.POST['name'] = name
        request.POST['page'] = page
        request.POST['publisher'] = publisher
        return request

    # def test_book_edit_can_save_a_post_request(self):
    #     name, page, publisher = 'name', 'page', 'publisher'
    #     request = self.post_request(name, page, publisher)
    #     response = index(request)
    #     self.assertFieldInResponse(response, name, page, publisher)
