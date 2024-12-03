from datetime import datetime

from bs4 import BeautifulSoup
from django.test import TestCase

from vietnam_research.domain.valueobject.vietkabu import Counting
from vietnam_research.management.commands.daily_import_from_vietkabu import (
    TransactionDate,
)
from vietnam_research.models import Symbol, IndClass, Market


class TestCounting(TestCase):

    def test_valid_value(self):
        c = Counting("1,000%")
        self.assertEqual(c.value, 1000.0)

    def test_empty_string(self):
        c = Counting("")
        self.assertEqual(c.value, 0.0)

    def test_invalid_value(self):
        with self.assertRaises(ValueError):
            c = Counting("-")


class TestTransactionDate(TestCase):
    @classmethod
    def setUpTestData(cls):
        Symbol.objects.create(
            code="AAA",
            name="アンファット・バイオプラスチック",
            ind_class=IndClass.objects.create(
                industry1="製造業", industry2="プラスチック製品", industry_class=1
            ),
            market=Market.objects.create(code="HOSE", name="ホーチミン証券取引所"),
        )

    def setUp(self):
        valid_html = (
            '<th colspan="20" class="table_list_left" bgcolor="#DDDDDD" '
            'style="text-align:left"><strong>&nbsp;ホーチミン証取株価</strong> '
            '(<b>2019/08/16 17:00VNT</b>)<span style="font-weight:normal;font-size:80%">'
            "※情報は毎日17時(ベトナム時間)に更新されます。</span><br>"
            '<span style="font-weight:normal"><span style="font-size:80%">'
            '※リアルタイム株価ボードはこちらからご覧ください。<br><a href="https://vntrade.fnsyrus.com/chung-khoan/danh-muc" '
            'target="_blank">https://vntrade.fnsyrus.com/chung-khoan/danh-muc</a></span></span></th>'
        )
        self.valid_th_tag = BeautifulSoup(valid_html, "html.parser").th

        invalid_html = (
            '<th colspan="20" class="table_list_left" bgcolor="#DDDDDD" '
            'style="text-align:left"><strong>&nbsp;ホーチミン証取株価</strong> '
            '(<b>カッコのない文字</b>)<span style="font-weight:normal;font-size:80%">'
            "※情報は毎日17時(ベトナム時間)に更新されます。</span><br>"
            '<span style="font-weight:normal"><span style="font-size:80%">'
            '※リアルタイム株価ボードはこちらからご覧ください。<br><a href="https://vntrade.fnsyrus.com/chung-khoan/danh-muc" '
            'target="_blank">https://vntrade.fnsyrus.com/chung-khoan/danh-muc</a></span></span></th>'
        )
        self.invalid_th_tag = BeautifulSoup(invalid_html, "html.parser").th

    def test_to_date(self):
        self.assertEqual(
            TransactionDate(self.valid_th_tag).to_date(),
            datetime(2019, 8, 16, 17, 0, 0),
        )

    def test_to_date_invalid_value(self):
        with self.assertRaises(ValueError):
            self.assertEqual(
                TransactionDate(self.invalid_th_tag).to_date(),
                datetime(2019, 8, 16, 17, 0),
            )
