import csv
import os
import shutil
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from soil_analysis.domain.repository.hardness_import_error import (
    HardnessImportErrorRepository,
)
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

        parse_result = HardnessImportService.parse_csv(csv_file)
        self.assertEqual(len(parse_result.rows), 2)
        rows = parse_result.rows
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

    def test_associate_with_ledger_updates_only_target_folder(self):
        """
        シナリオ:
        - 入力: 関連付け対象フォルダと別フォルダの硬度測定データ。
        - 処理: 対象フォルダだけを指定して台帳へ関連付ける。
        - 期待値: 対象フォルダだけに台帳・圃場ブロックが設定され、別フォルダは未設定のまま残ること。
        """
        dt = datetime(2023, 7, 1, 10, 0, 0)
        for folder_name, memory_offset in (
            ("target_folder", 100),
            ("other_folder", 200),
        ):
            for depth in range(1, 3):
                SoilHardnessMeasurement.objects.create(
                    set_device=self.device,
                    set_memory=memory_offset,
                    set_datetime=dt,
                    set_depth=2,
                    set_spring=1,
                    set_cone=1,
                    depth=depth,
                    pressure=100,
                    folder=folder_name,
                )

        success = HardnessImportService.associate_with_ledger(
            "target_folder", self.ledger.id
        )

        self.assertTrue(success)
        self.assertEqual(
            SoilHardnessMeasurement.objects.filter(
                folder="target_folder", land_ledger=self.ledger
            ).count(),
            2,
        )
        self.assertEqual(
            SoilHardnessMeasurement.objects.filter(
                folder="other_folder", land_ledger__isnull=True, land_block__isnull=True
            ).count(),
            2,
        )

    def test_save_import_data_records_duplicate_as_import_error(self):
        """
        シナリオ:
        - 入力: set_device・set_memory・set_datetime・depth が同一の硬度行を2回保存する。
        - 処理: 1回目で作成し、2回目で一意制約に衝突させる。
        - 期待値: 2回目は作成されず、取り込み済みエラーとして記録されること。
        """
        dt = datetime(2023, 7, 1, 10, 0, 0)
        row = HardnessRow(
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

        first_result = HardnessImportService.save_import_data([row])
        second_result = HardnessImportService.save_import_data([row])

        self.assertEqual(first_result["created"], 1)
        self.assertEqual(second_result["created"], 0)
        self.assertEqual(
            HardnessImportErrorRepository.get_all()[0].message, "取り込み済み"
        )

    def test_generate_dummy_csv_command_creates_two_upload_zips_without_overlap(self):
        """
        シナリオ:
        - 入力: want_to_create_dataset_round=2, num_fields=2 を指定する。
        - 処理: 硬度ダミーCSV生成コマンドを実行する。
        - 期待値: 2つの投入用ZIPが生成され、フォルダ名・測定日時・メモリ番号が重複しないこと。
        """
        output_path = Path(
            call_command(
                "hardness_generate_dummy_csv",
                "--num_fields=2",
                "--want_to_create_dataset_round=2",
            )
        )
        self.addCleanup(lambda: shutil.rmtree(output_path.parent, ignore_errors=True))

        stage1_zip = output_path / "hardness_upload_01.zip"
        stage2_zip = output_path / "hardness_upload_02.zip"
        self.assertTrue(stage1_zip.exists())
        self.assertTrue(stage2_zip.exists())

        stage1_folders, stage1_datetimes, stage1_memories = self._inspect_upload_zip(
            stage1_zip
        )
        stage2_folders, stage2_datetimes, stage2_memories = self._inspect_upload_zip(
            stage2_zip
        )

        self.assertTrue(stage1_folders.isdisjoint(stage2_folders))
        self.assertTrue(stage1_datetimes.isdisjoint(stage2_datetimes))
        self.assertTrue(stage1_memories.isdisjoint(stage2_memories))

    @staticmethod
    def _inspect_upload_zip(zip_path: Path) -> tuple[set[str], set[str], set[int]]:
        folders = set()
        datetimes = set()
        memories = set()
        with zipfile.ZipFile(zip_path) as archive:
            csv_names = [name for name in archive.namelist() if name.endswith(".csv")]
            for csv_name in csv_names:
                folders.add(csv_name.replace("\\", "/").split("/")[0])
                with archive.open(csv_name) as csv_file:
                    rows = list(csv.reader(line.decode() for line in csv_file))
                memories.add(int(rows[1][1]))
                datetimes.add(rows[5][1])
        return folders, datetimes, memories
