from datetime import datetime

from bs4 import BeautifulSoup
from django.test import TestCase

from vietnam_research.domain.valueobject.vietkabu import Counting, MarketDataRow
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
        c = Counting("-")
        self.assertEqual(c.value, None)


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


class TestMarketDataRow(TestCase):
    def test_market_data_row_from_html(self):
        html = """
        <tr bgcolor="#FFFFFF" id="APG" onmouseover="on_over('APG','#DDEFFF')" onmouseout="on_out('APG','#FFFFFF')" style="background: rgb(255, 255, 255);">
            <td width="65" class="table_list_center">
                <a title="APG証券" href="/hcm/APG.html">
                APG     </a>
            </td>
            <td width="55" nowrap="" class="table_list_right">
                <b>8.99</b>
            </td>
            <td width="55" nowrap="" class="table_list_right">
                <b>9.04</b>
            </td>
            <td width="55" nowrap="" class="table_list_right">
                <b>8.88</b>
            </td>
            <td width="55" nowrap="" class="table_list_right">
                <b>9.04</b>
            </td>
            <td width="55" nowrap="" class="table_list_right">
                <b>8.8</b>
            </td>   	         
            <td width="62" nowrap="" class="table_list_right"><span style="color:#006600">+50</span></td>
            <td width="65" nowrap="" class="table_list_right"><span style="color:#006600">+0.56%</span></td>
            <td width="62" nowrap="" class="table_list_right">304,300</td>
            <td width="110" nowrap="" class="table_list_right">2,021,542</td>
            <td width="88" nowrap="" class="table_list_right">128.76</td>
            <td width="52" nowrap="" class="table_list_right">11.11</td>
            <td width="75" nowrap="" class="table_list_right">0</td>
            <td width="75" nowrap="" class="table_list_right">0</td>
            <td width="84" nowrap="" class="table_list_center">
               <img title="金融業[証券業]" src="/images/stock/fnc.gif" width="28" height="13" style="margin:0 4px;"> </td>
        </tr>
        """
        soup = BeautifulSoup(html, "html.parser")
        tr = soup.find("tr")
        row = MarketDataRow(tr)
        # These values are checked using the html snippet above.
        self.assertEqual(row.code, "APG")
        self.assertEqual(row.name, "APG証券")
        self.assertEqual(row.industry_title, "金融業[証券業]")
        self.assertEqual(row.industry1, "金融業")
        self.assertEqual(row.industry2, "証券業")
        self.assertEqual(row.open_price, 8.88)
        self.assertEqual(row.high_price, 9.04)
        self.assertEqual(row.low_price, 8.8)
        self.assertEqual(row.closing_price, 9.04)
        self.assertEqual(row.volume, 304300)
        self.assertEqual(row.marketcap, 128.76)
        self.assertEqual(row.per, 11.11)
