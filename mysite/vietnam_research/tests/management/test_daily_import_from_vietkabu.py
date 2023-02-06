from bs4 import BeautifulSoup
from django.test import TestCase
from django.utils.datetime_safe import datetime

from vietnam_research.management.commands.daily_import_from_vietkabu import retrieve_transaction_date, extract_newcomer
from vietnam_research.models import Symbol, IndClass, Market


class Test(TestCase):
    def setUp(self) -> None:
        Symbol.objects.create(
            code='AAA',
            name='アンファット・バイオプラスチック',
            ind_class=IndClass.objects.create(industry1='製造業', industry2='プラスチック製品', industry_class=1),
            market=Market.objects.create(code='HOSE', name='ホーチミン証券取引所'))

    def test_retrieve_market_date(self):
        self.assertEqual(retrieve_transaction_date('ホーチミン証取株価（2019/08/16 VNT）'), datetime(2019, 8, 16, 17, 0, 0))

        res = retrieve_transaction_date('ホーチミン証取株価（2019/08/16 VNT）')
        self.assertEqual(res.year, 2019)
        self.assertEqual(res.month, 8)
        self.assertEqual(res.day, 16)
        self.assertEqual(res.hour, 17)
        self.assertEqual(res.minute, 0)
        self.assertEqual(res.second, 0)

    def test_retrieve_market_date_invalid_value(self):
        with self.assertRaises(ValueError):
            self.assertEqual(retrieve_transaction_date('カッコのない文字'), datetime(2019, 8, 16, 17, 0))

    def test_extract_newcomer(self):
        """
        最初の tr は既存。ふたつめの tr は新規
        """
        source = """
            <tr bgcolor="#FFFFFF" id="AAA" onmouseover="on_over('AAA','#DDEFFF')">
                <td id="c1" class="table_list_center">  
                    <a title="アンファット・バイオプラスチック" href="/hcm/AAA.html">   AAA<a name="A"></a>
                </td>
                <td nowrap id="c2" class="table_list_right"><b>8.30</b></td>
                    <td nowrap id="c3" class="table_list_right"><b>8.10</b></td>
                    <td nowrap id="c4" class="table_list_right"><b>8.41</b>
                </td>
                <td nowrap id="c5" class="table_list_right"><b>8.50</b></td>
                <td nowrap id="c6" class="table_list_right">
                    <b>8.06</b>
                </td>
                <td nowrap id="c7" class="table_list_right"><span style='color:red'>-200</span></td>
                <td nowrap id="c8" class="table_list_right"><span style='color:red'>-2.41%</span></td>
                <td nowrap id="c9" class="table_list_right">4,343,500</td>
                <td nowrap id="c10" class="table_list_right">35,989,790</td>
                <td nowrap id="c11" class="table_list_right">3,096,423</td>
                <td nowrap id="c12" class="table_list_right">172.98</td>
                <td nowrap id="c13" class="table_list_right">3.01</td>
                <td nowrap id="c14" class="table_list_right">-</td>
                <td nowrap id="c15" class="table_list_right">-</td>
                <td nowrap id="c16" class="table_list_center">
                <img title="製造業[プラスチック製品]" src="/images/stock/mnf.gif" width="28" style="margin:0 4px;"/>
                </td>
            </tr>
            <tr bgcolor="#FFFFFF" id="AAA999" onmouseover="on_over('AAA999','#DDEFFF')">
                <td id="c1" class="table_list_center">  
                     <a title="アンファット・バイオプラスチック" href="/hcm/AAA999.html">   AAA999<a name="A"></a>
                </td>
                <td nowrap id="c2" class="table_list_right"><b>8.30</b></td>
                <td nowrap id="c3" class="table_list_right"><b>8.10</b></td>
                <td nowrap id="c4" class="table_list_right"><b>8.41</b></td>
                <td nowrap id="c5" class="table_list_right"><b>8.50</b></td>
                <td nowrap id="c6" class="table_list_right"><b>8.06</b></td>
                <td nowrap id="c7" class="table_list_right"><span style='color:red'>-200</span></td>
                <td nowrap id="c8" class="table_list_right"><span style='color:red'>-2.41%</span></td>
                <td nowrap id="c9" class="table_list_right">4,343,500</td>
                <td nowrap id="c10" class="table_list_right">35,989,790</td>
                <td nowrap id="c11" class="table_list_right">3,096,423</td>
                <td nowrap id="c12" class="table_list_right">172.98</td>
                <td nowrap id="c13" class="table_list_right">3.01</td>
                <td nowrap id="c14" class="table_list_right">-</td>
                <td nowrap id="c15" class="table_list_right">-</td>
                <td nowrap id="c16" class="table_list_center">
                <img title="製造業[プラスチック製品]" src="/images/stock/mnf.gif" width="28" style="margin:0 4px;"/>
                </td>
            </tr>
        """
        soup = BeautifulSoup(source, 'lxml')
        m_symbol = Symbol.objects.filter(market__code='HOSE')
        m_ind_class = IndClass.objects.get(industry1='製造業', industry2='プラスチック製品')
        expected = [
            {'symbol': 'AAA999', 'name': 'アンファット・バイオプラスチック', 'industry': m_ind_class}
        ]
        self.assertEqual(extract_newcomer(soup, m_symbol), expected)

    def test_extract_newcomer_invalid_value(self):
        """
        vietkabuに 製造業[] のような不正な業種データが入っていることがあった。除外したい
        """
        source = """
            <tr bgcolor="#FFFFFF" id="AAT999" onmouseover="on_over('AAT999','#DDEFFF')">
                <td class="table_list_center">  
                     <a title="ティエンソン・タインホア" href="/hcm/AAT999.html">AAT999       </a>
                </td>
                <td nowrap class="table_list_right">
                    <b>5.47</b>
                </td>
                 <td nowrap class="table_list_right">
                    <b>5.45</b>
                </td>
                 <td nowrap class="table_list_right">
                    <b>5.50</b>
                </td>
                 <td nowrap class="table_list_right">
                    <b>5.64</b>
                </td>
                <td nowrap class="table_list_right">
                    <b>5.37</b>
                </td>
                <td nowrap class="table_list_right"><span style='color:red'>-20</span></td>
                <td nowrap class="table_list_right"><span style='color:red'>-0.37%</span></td>
                <td nowrap class="table_list_right">1,156,300</td>
                <td nowrap class="table_list_right">6,292,320</td>
                <td nowrap class="table_list_right">347,718</td>
                <td nowrap class="table_list_right">19.43</td>
                <td nowrap class="table_list_right">8.96</td>
                <td nowrap class="table_list_right">-</td>
                <td nowrap class="table_list_right">-</td>
                <td nowrap class="table_list_center">
                <img title="製造業[]" src="/images/stock/mnf.gif" width="28" height="13" style="margin:0 4px;"/>
                </td>
            </tr>
        """
        soup = BeautifulSoup(source, 'lxml')
        m_symbol = Symbol.objects.filter(market__code='HOSE')
        self.assertEqual(len(extract_newcomer(soup, m_symbol)), 0)
