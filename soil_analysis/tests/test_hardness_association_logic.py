import csv
import os
import shutil
import tempfile
from datetime import datetime

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from soil_analysis.domain.repository.hardness_measurement import (
    SoilHardnessMeasurementRepository,
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
)


class HardnessAssociationLogicTest(TestCase):
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
        self.temp_dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.temp_dir)

    def create_csv(self, folder_name, memory_no, dt_str):
        folder_path = os.path.join(self.temp_dir, folder_name)
        os.makedirs(folder_path, exist_ok=True)
        csv_file = os.path.join(folder_path, f"data_{memory_no}.csv")
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["DIK-5531", "Digital Cone Penetrometer"])
            writer.writerow(["Memory No.", memory_no])
            writer.writerow(["Latitude", "0"])
            writer.writerow(["Longitude", "0"])
            writer.writerow(["Set Depth", "50"])
            writer.writerow(["Date and Time", dt_str])
            writer.writerow(["Spring", "1"])
            writer.writerow(["Cone", "1"])
            writer.writerow([])
            writer.writerow(["Depth", "Pressure"])
            writer.writerow(["1", "100"])
            writer.writerow(["2", "200"])
        return csv_file

    def test_only_unassociated_groups_returned(self):
        # 1. 最初の5圃場分（相当）をインポート
        self.create_csv("Folder1", 1, " 23.07.01 10:00:00")
        call_command("hardness_load_data", self.temp_dir)

        # 2. 紐付けを行う (land_block もセットする)
        from soil_analysis.models import LandBlock

        block = LandBlock.objects.create(name="A1")
        measurements = SoilHardnessMeasurement.objects.filter(folder="Folder1")
        for m in measurements:
            m.land_ledger = self.ledger
            m.land_block = block
            m.save()

        # 3. 2ラウンド目: 新しい4圃場分（相当）をインポート
        self.create_csv("Folder2", 2, " 23.07.02 10:00:00")
        call_command("hardness_load_data", self.temp_dir)

        # 4. 検証: get_folder_groups_for_association が Folder2 のみを返すこと
        groups = SoilHardnessMeasurementRepository.get_folder_groups_for_association()

        # Folder1 は land_block が入っているので除外され、Folder2 のみとなる
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["folder_name"], "Folder2")

        # 5. 進捗カウントの検証 (こちらは全件対象のロジックを期待)
        total = SoilHardnessMeasurementRepository.get_total_groups_count()
        processed = SoilHardnessMeasurementRepository.get_processed_groups_count()
        self.assertEqual(total, 2)
        self.assertEqual(processed, 1)
