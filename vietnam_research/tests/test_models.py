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
            code="AAA",
            name="アンファット・バイオプラスチック",
            ind_class=IndClass.objects.create(
                industry1="農林水産業", industry2="天然ゴム", industry_class=1
            ),
            market=Market.objects.create(code="HOSE", name="ホーチミン証券取引所"),
        )

    def test_table_has_zero_records(self):
        self.assertEqual(Industry.objects.all().count(), 0)

    def test_record_count_is_one(self):
        Industry.objects.create(
            recorded_date="2022-03-01",
            open_price=12.4,
            high_price=12.65,
            low_price=12.25,
            closing_price=12.5,
            volume=2037710.0,
            marketcap=100.0,
            per=6.76,
            created_at=now(),
            symbol=Symbol.objects.get(code="AAA"),
        )
        self.assertEqual(Industry.objects.all().count(), 1)

    def test_matches_before_saving(self):
        market = Market.objects.get(code="HOSE")
        symbol = Symbol.objects.get(code="AAA")
        ind_class = IndClass.objects.get(industry1="農林水産業", industry2="天然ゴム")
        Industry.objects.create(
            recorded_date="2023-02-02",
            open_price=12.4,
            high_price=12.65,
            low_price=12.25,
            closing_price=12.5,
            volume=2037710.0,
            marketcap=100.0,
            per=6.76,
            created_at=now(),
            symbol=Symbol.objects.get(code="AAA"),
        )
        industry = Industry.objects.filter(recorded_date="2023-02-02").get(
            symbol__code="AAA"
        )
        self.assertEqual(industry.symbol.market, market)
        self.assertEqual(industry.symbol, symbol)
        self.assertEqual(industry.symbol.ind_class, ind_class)

    def test_slipped_month_end(self):
        Industry.objects.create(
            recorded_date="2022-02-28",
            open_price=12.4,
            high_price=12.65,
            low_price=12.25,
            closing_price=12.5,
            volume=2037710.0,
            marketcap=100.0,
            per=6.76,
            created_at=now(),
            symbol=Symbol.objects.get(code="AAA"),
        )
        expected_value = datetime.date(2022, 2, 28)
        self.assertEqual(
            Industry.objects.slipped_month_end(
                -1, datetime.datetime(2022, 3, 15)
            ).recorded_date,
            expected_value,
        )
