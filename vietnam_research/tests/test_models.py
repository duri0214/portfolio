from datetime import datetime

from django.test import TestCase
from django.utils.timezone import now

from vietnam_research.models import Industry, Market, Symbol, IndClass


class TestIndustry(TestCase):
    def test_table_has_zero_records(self):
        self.assertEqual(Industry.objects.all().count(), 0)

    def test_record_count_is_one(self):
        symbol = Symbol.objects.create(
            code="AAA",
            name="アンファット・バイオプラスチック",
            ind_class=IndClass.objects.create(
                industry1="農林水産業", industry2="天然ゴム", industry_class=1
            ),
            market=Market.objects.create(code="HOSE", name="ホーチミン証券取引所"),
        )
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
            symbol=symbol,
        )
        self.assertEqual(Industry.objects.all().count(), 1)

    def test_matches_before_saving(self):
        market = Market.objects.create(code="HOSE", name="ホーチミン証券取引所")
        symbol = Symbol.objects.create(
            code="AAA",
            name="アンファット・バイオプラスチック",
            ind_class=IndClass.objects.create(
                industry1="農林水産業", industry2="天然ゴム", industry_class=1
            ),
            market=market,
        )
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
            symbol=symbol,
        )
        industry = Industry.objects.filter(recorded_date="2023-02-02").get(
            symbol__code="AAA"
        )
        self.assertEqual(industry.symbol.market, market)
        self.assertEqual(industry.symbol, symbol)
        self.assertEqual(industry.symbol.ind_class.industry1, "農林水産業")
        self.assertEqual(industry.symbol.ind_class.industry2, "天然ゴム")

    def test_slipped_month_end(self):
        symbol = Symbol.objects.create(
            code="AAA",
            name="アンファット・バイオプラスチック",
            ind_class=IndClass.objects.create(
                industry1="農林水産業", industry2="天然ゴム", industry_class=1
            ),
            market=Market.objects.create(code="HOSE", name="ホーチミン証券取引所"),
        )
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
            symbol=symbol,
        )
        expected_value = datetime(2022, 2, 28).date()
        result = Industry.objects.slipped_month_end(-1, datetime(2022, 3, 15))
        self.assertEqual(result.recorded_date, expected_value)
