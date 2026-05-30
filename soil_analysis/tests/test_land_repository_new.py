from django.test import TestCase

from soil_analysis.domain.repository.land import LandRepository
from soil_analysis.models import Company, Land, LandLedger, LandPeriod


class LandRepositoryTest(TestCase):
    def setUp(self):
        self.company = Company.objects.create(name="Test Company")
        self.land1 = Land.objects.create(name="Land 1", company=self.company)
        self.land2 = Land.objects.create(name="Land 2", company=self.company)
        self.period = LandPeriod.objects.create(year=2024, name="Spring")
        self.ledger1 = LandLedger.objects.create(
            land=self.land1, land_period=self.period
        )
        self.ledger2 = LandLedger.objects.create(
            land=self.land1,
            land_period=LandPeriod.objects.create(year=2023, name="Spring"),
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
