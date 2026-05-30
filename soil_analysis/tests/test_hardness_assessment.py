from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from soil_analysis.domain.service.hardness_measurement_service import (
    HardnessMeasurementService,
)
from soil_analysis.models import (
    LandLedger,
    LandBlock,
    SoilHardnessMeasurement,
    Land,
    Company,
    CompanyCategory,
    LandPeriod,
    Device,
    JmaArea,
    JmaPrefecture,
    JmaRegion,
    JmaCity,
    CultivationType,
    Crop,
    SamplingMethod,
)


class HardnessAssessmentTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="testuser")
        self.category = CompanyCategory.objects.create(name="Test Category")
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

        self.land = Land.objects.create(
            name="Test Land",
            company=self.company,
            jma_city=self.city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
            center="36.0,140.0",
        )
        self.period = LandPeriod.objects.create(name="Test Period", year=2024)
        self.ledger = LandLedger.objects.create(
            land=self.land,
            land_period=self.period,
            sampling_date=date(2024, 4, 1),
            analytical_agency=self.company,
            crop=self.crop,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )
        self.device = Device.objects.create(name="Test Device")
        self.block_a1 = LandBlock.objects.get_or_create(name="A1")[0]
        self.block_b1 = LandBlock.objects.get_or_create(name="B1")[0]

    def test_get_hardness_assessment_with_data(self):
        # A1ブロックにデータを追加 (平均 1000)
        SoilHardnessMeasurement.objects.create(
            land_ledger=self.ledger,
            land_block=self.block_a1,
            set_device=self.device,
            set_memory=1,
            set_datetime=timezone.now(),
            set_depth=60,
            set_spring=1,
            set_cone=1,
            depth=10,
            pressure=800,
            folder="test",
        )
        SoilHardnessMeasurement.objects.create(
            land_ledger=self.ledger,
            land_block=self.block_a1,
            set_device=self.device,
            set_memory=1,
            set_datetime=timezone.now(),
            set_depth=60,
            set_spring=1,
            set_cone=1,
            depth=20,
            pressure=1200,
            folder="test",
        )

        # B1ブロックにデータを追加 (平均 3000)
        SoilHardnessMeasurement.objects.create(
            land_ledger=self.ledger,
            land_block=self.block_b1,
            set_device=self.device,
            set_memory=2,
            set_datetime=timezone.now(),
            set_depth=60,
            set_spring=1,
            set_cone=1,
            depth=10,
            pressure=3000,
            folder="test",
        )

        assessment = HardnessMeasurementService.get_hardness_assessment(self.ledger)

        # A1の判定
        a1_assessment = assessment.get_block("A1")
        self.assertEqual(a1_assessment.avg_pressure, 1000)
        self.assertEqual(a1_assessment.assessment_category, "good")
        self.assertEqual(a1_assessment.display_value, "1,000")
        # 深度データ
        self.assertEqual(len(a1_assessment.depth_pressures), 2)
        self.assertEqual(a1_assessment.depth_pressures[0], (10, 800))
        self.assertEqual(a1_assessment.depth_pressures[1], (20, 1200))
        self.assertTrue("16.7,80.0 33.3,70.0" in a1_assessment.sparkline_points)

        # B1の判定
        b1_assessment = assessment.get_block("B1")
        self.assertEqual(b1_assessment.avg_pressure, 3000)
        self.assertEqual(b1_assessment.assessment_category, "bad")
        self.assertEqual(b1_assessment.display_value, "3,000")
        self.assertEqual(len(b1_assessment.depth_pressures), 1)

        # C1 (データなし) の判定
        c1_assessment = assessment.get_block("C1")
        self.assertIsNone(c1_assessment.avg_pressure)
        self.assertEqual(c1_assessment.assessment_category, "none")
        self.assertEqual(c1_assessment.display_value, "-")
        self.assertEqual(len(c1_assessment.depth_pressures), 0)
        self.assertEqual(c1_assessment.sparkline_points, "")
