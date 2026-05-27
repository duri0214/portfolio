import csv
import os
import shutil
import tempfile
from datetime import datetime

from django.contrib.auth import get_user_model
from django.test import TestCase

from soil_analysis.domain.service.hardness_import_service import (
    HardnessImportService,
    HardnessRow,
)
from soil_analysis.models import (
    SoilHardnessMeasurement,
    Device,
    Land,
    LandLedger,
    Company,
    CompanyCategory,
    Crop,
    LandPeriod,
    JmaArea,
    JmaPrefecture,
    JmaRegion,
    JmaCity,
    CultivationType,
    SamplingMethod,
    SamplingOrder,
    LandBlock,
)


class HardnessImportServiceTest(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="testuser")
        self.device = Device.objects.create(name="DIK-5531")

        # マスタ類の作成
        category = CompanyCategory.objects.create(name="Test Category")
        self.company = Company.objects.create(name="Test Company", category=category)

        area = JmaArea.objects.create(code="01", name="Test Area")
        pref = JmaPrefecture.objects.create(
            code="0101", name="Test Pref", jma_area=area
        )
        region = JmaRegion.objects.create(
            code="010101", name="Test Region", jma_prefecture=pref
        )
        self.city = JmaCity.objects.create(
            code="0101011", name="Test City", jma_region=region
        )

        self.cultivation_type = CultivationType.objects.create(name="Open Field")
        self.crop = Crop.objects.create(name="Test Crop")
        self.period = LandPeriod.objects.create(year=2023, name="2023")
        self.sampling_method = SamplingMethod.objects.create(name="5-point", times=5)

        self.land = Land.objects.create(
            name="Field A",
            company=self.company,
            jma_city=self.city,
            cultivation_type=self.cultivation_type,
            owner=self.user,
        )
        self.ledger = LandLedger.objects.create(
            land=self.land,
            crop=self.crop,
            land_period=self.period,
            sampling_date=datetime(2023, 7, 1).date(),
            analytical_agency=self.company,
            sampling_method=self.sampling_method,
            sampling_staff=self.user,
        )

        # SamplingOrder and LandBlock for association test
        self.block1 = LandBlock.objects.create(name="A1")
        SamplingOrder.objects.create(
            sampling_method=self.sampling_method, land_block=self.block1, ordering=1
        )

        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def create_csv_content(self, memory_no, dt_str):
        return [
            ["DIK-5531", "Digital Cone Penetrometer"],
            ["Memory No.", memory_no],
            ["Latitude", "0"],
            ["Longitude", "0"],
            ["Set Depth", "50"],
            ["Date and Time", dt_str],
            ["Spring", "1"],
            ["Cone", "1"],
            [],
            ["Depth", "Pressure"],
            ["1", "100"],
            ["2", "200"],
        ]

    def test_parse_csv(self):
        folder_path = os.path.join(self.temp_dir, "Folder1")
        os.makedirs(folder_path, exist_ok=True)
        csv_file = os.path.join(folder_path, "data_1.csv")
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerows(self.create_csv_content(1, " 23.07.01 10:00:00"))

        rows = HardnessImportService.parse_csv(csv_file)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].set_device_name, "DIK-5531")
        self.assertEqual(rows[0].folder, "Folder1")
        self.assertEqual(rows[0].depth, 1)
        self.assertEqual(rows[0].pressure, 100)

    def test_save_import_data(self):
        dt = datetime(2023, 7, 1, 10, 0, 0)
        rows = [
            HardnessRow(
                set_device_name="DIK-5531",
                set_memory=1,
                set_datetime=dt,
                set_depth=50,
                set_spring=1,
                set_cone=1,
                depth=1,
                pressure=100,
                folder="Folder1",
                file_name="data_1.csv",
            )
        ]
        result = HardnessImportService.save_import_data(rows)
        self.assertEqual(result["created"], 1)
        self.assertTrue(
            SoilHardnessMeasurement.objects.filter(folder="Folder1").exists()
        )

    def test_get_suitable_ledgers(self):
        # Name match
        ledgers = HardnessImportService.get_suitable_ledgers("Field A_2023")
        self.assertIn(self.ledger, ledgers)

        # Already used should be excluded
        SoilHardnessMeasurement.objects.create(
            set_device=self.device,
            set_memory=1,
            set_datetime=datetime.now(),
            set_depth=50,
            set_spring=1,
            set_cone=1,
            depth=1,
            pressure=100,
            folder="Folder1",
            land_ledger=self.ledger,
        )
        ledgers = HardnessImportService.get_suitable_ledgers("Field A_2023")
        self.assertNotIn(self.ledger, ledgers)

    def test_associate_with_ledger(self):
        # Create some measurements
        dt = datetime(2023, 7, 1, 10, 0, 0)
        for i in range(
            1, 11
        ):  # 10 records, max_depth=10, so 10*1=10 -> should fill 1 block (if SAMPLING_TIMES_PER_BLOCK=5, then 2 samplings?)
            # Wait, records_per_block = max_depth * SAMPLING_TIMES_PER_BLOCK
            # If max_depth=2 and SAMPLING_TIMES_PER_BLOCK=5, then 10 records per block.
            SoilHardnessMeasurement.objects.create(
                set_device=self.device,
                set_memory=1,
                set_datetime=dt,
                set_depth=2,
                set_spring=1,
                set_cone=1,
                depth=i,  # Use i to keep it unique
                pressure=100,
                folder="Folder_to_associate",
            )

        success = HardnessImportService.associate_with_ledger(
            "Folder_to_associate", self.ledger.id
        )
        self.assertTrue(success)

        measurements = SoilHardnessMeasurement.objects.filter(
            folder="Folder_to_associate"
        )
        for m in measurements:
            self.assertEqual(m.land_ledger, self.ledger)
            self.assertEqual(m.land_block, self.block1)
