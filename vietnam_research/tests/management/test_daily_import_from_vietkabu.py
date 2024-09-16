from datetime import datetime

from django.test import TestCase

from vietnam_research.management.commands.daily_import_from_vietkabu import (
    convert_to_datetime,
)
from vietnam_research.models import Symbol, IndClass, Market


class Test(TestCase):
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

    def test_convert_to_datetime(self):
        self.assertEqual(
            convert_to_datetime("ホーチミン証取株価（2019/08/16 17:00VNT）"),
            datetime(2019, 8, 16, 17, 0, 0),
        )

        res = convert_to_datetime("ホーチミン証取株価（2019/08/16 17:00VNT）")
        self.assertEqual(res.year, 2019)
        self.assertEqual(res.month, 8)
        self.assertEqual(res.day, 16)
        self.assertEqual(res.hour, 17)
        self.assertEqual(res.minute, 0)
        self.assertEqual(res.second, 0)

    def test_convert_to_datetime_invalid_value(self):
        with self.assertRaises(ValueError):
            self.assertEqual(
                convert_to_datetime("カッコのない文字"),
                datetime(2019, 8, 16, 17, 0),
            )
