import datetime
from django.test import TestCase

from django.utils.timezone import now

from vietnam_research.models import Industry, Market, Symbol, IndClass


class TestIndustry(TestCase):
    """
    Notes: PyCharmのunittest経由だと失敗します（Requested setting INSTALLED_APPS ...）
    `python manage.py test vietnam_research` でテストできます
    """
    def setUp(self) -> None:
        Symbol.objects.create(
            code='AAA',
            name='アンファット・バイオプラスチック',
            ind_class=IndClass.objects.create(industry1='農林水産業', industry2='天然ゴム', industry_class=1),
            market=Market.objects.create(code='HOSE', name='ホーチミン証券取引所'))

    def test_table_has_zero_records(self):
        self.assertEqual(Industry.objects.all().count(), 0)

    def test_record_count_is_one(self):
        Industry.objects.create(
            recorded_date='2022-03-01',
            market=Market.objects.get(code='HOSE'),
            symbol=Symbol.objects.get(code='AAA'),
            ind_class=IndClass.objects.get(industry1='農林水産業', industry2='天然ゴム'),
            created_at=now()
        )
        self.assertEqual(Industry.objects.all().count(), 1)

    def test_matches_before_saving(self):
        market = Market.objects.get(code='HOSE')
        symbol = Symbol.objects.get(code='AAA')
        ind_class = IndClass.objects.get(industry1='農林水産業', industry2='天然ゴム')
        Industry.objects.create(
            recorded_date='2023-02-02',
            market=market,
            symbol=symbol,
            ind_class=ind_class,
            created_at=now()
        )
        industry = Industry.objects.filter(recorded_date='2023-02-02').get(symbol__code='AAA')
        self.assertEqual(industry.market, market)
        self.assertEqual(industry.symbol, symbol)
        self.assertEqual(industry.ind_class, ind_class)

    def test_slipped_month_end(self):
        Industry.objects.create(
            recorded_date='2022-02-28',
            market=Market.objects.get(code='HOSE'),
            symbol=Symbol.objects.get(code='AAA'),
            ind_class=IndClass.objects.get(industry1='農林水産業', industry2='天然ゴム'),
            created_at=now()
        )
        expected_value = datetime.date(2022, 2, 28)
        self.assertEqual(Industry.objects.slipped_month_end(-1, datetime.datetime(2022, 3, 15)).recorded_date, expected_value)
