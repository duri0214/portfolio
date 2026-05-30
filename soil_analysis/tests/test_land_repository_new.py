from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase

from soil_analysis.domain.repository.land import LandRepository
from soil_analysis.models import (
    Company,
    CompanyCategory,
    Crop,
    CultivationType,
    JmaArea,
    JmaCity,
    JmaPrefecture,
    JmaRegion,
    Land,
    LandLedger,
    LandPeriod,
    SamplingMethod,
)


class LandRepositoryTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="testuser")
        self.category = CompanyCategory.objects.create(name="農業法人")
        self.company = Company.objects.create(
            name="Test Company", category=self.category
        )

        area = JmaArea.objects.create(code="01", name="テストエリア")
        pref = JmaPrefecture.objects.create(code="0101", name="テスト県", jma_area=area)
        region = JmaRegion.objects.create(
            code="010101", name="テスト地域", jma_prefecture=pref
        )
        self.city = JmaCity.objects.create(
            code="0101011", name="テスト市", jma_region=region
        )
        self.cultivation_type = CultivationType.objects.create(name="露地")
        self.crop = Crop.objects.create(name="キャベツ")
        self.sampling_method = SamplingMethod.objects.create(name="5点法", times=5)

        self.land1 = Land.objects.create(
            name="Land 1",
            company=self.company,
            jma_city=self.city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
        )
        self.land2 = Land.objects.create(
            name="Land 2",
            company=self.company,
            jma_city=self.city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
        )
        self.period = LandPeriod.objects.create(year=2024, name="Spring")
        self.ledger1 = LandLedger.objects.create(
            land=self.land1,
            land_period=self.period,
            sampling_date=date(2024, 4, 1),
            analytical_agency=self.company,
            crop=self.crop,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )
        self.period2 = LandPeriod.objects.create(year=2023, name="Spring")
        self.ledger2 = LandLedger.objects.create(
            land=self.land1,
            land_period=self.period2,
            sampling_date=date(2023, 4, 1),
            analytical_agency=self.company,
            crop=self.crop,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )

    def test_get_land_to_ledgers_map(self):
        lands = [self.land1, self.land2]
        ledger_map = LandRepository.get_land_to_ledgers_map(lands)

        self.assertEqual(len(ledger_map), 2)
        self.assertIn(self.land1.id, ledger_map)
        self.assertIn(self.land2.id, ledger_map)

        self.assertEqual(len(ledger_map[self.land1.id]), 2)
        self.assertEqual(len(ledger_map[self.land2.id]), 0)

        # 降順に並んでいるか確認 (2024 -> 2023)
        self.assertEqual(ledger_map[self.land1.id][0].land_period.year, 2024)
        self.assertEqual(ledger_map[self.land1.id][1].land_period.year, 2023)
