import csv
import dataclasses
import os
from datetime import datetime
from typing import List, Dict, Any

import pytz
from django.db import transaction, IntegrityError
from django.utils import timezone

from soil_analysis.models import (
    SoilHardnessMeasurement,
    SoilHardnessMeasurementImportErrors,
    Device,
    LandLedger,
    Land,
    SamplingOrder,
)


@dataclasses.dataclass(frozen=True)
class HardnessRow:
    """土壌硬度データをパースしたデータ行"""

    set_device_name: str
    set_memory: int
    set_datetime: datetime
    set_depth: int
    set_spring: int
    set_cone: int
    depth: int
    pressure: int
    folder: str
    file_name: str


class HardnessImportService:
    SAMPLING_TIMES_PER_BLOCK = 5

    @staticmethod
    def extract_device(line: list) -> str:
        value = line[1].strip()
        if value != "Digital Cone Penetrometer":
            raise ValueError(f"unexpected data row: {value}")

        value = line[0].strip()
        if not value.startswith("DIK-"):
            raise ValueError(f"unexpected device name: {value}")

        return value

    @staticmethod
    def extract_datetime(line: list) -> datetime:
        value = line[0].strip()
        if value != "Date and Time":
            raise ValueError(f"unexpected data row: {value}")

        value = line[1].strip()
        try:
            value = pytz.timezone("Asia/Tokyo").localize(
                datetime.strptime(value, "%y.%m.%d %H:%M:%S")
            )
        except ValueError:
            raise ValueError(f"unexpected datetime: {value}")

        return value

    @staticmethod
    def extract_numeric_value(line: list) -> int:
        value = line[0].strip()
        if not any(
            value.startswith(prefix)
            for prefix in ("Memory No.", "Set Depth", "Spring", "Cone")
        ):
            raise ValueError(f"unexpected data row: {value}")

        value = line[1].strip()
        try:
            value = int(value)
        except ValueError:
            raise ValueError(f"unexpected numeric value: {value}")
        return value

    @classmethod
    def parse_csv(cls, file_path: str) -> List[HardnessRow]:
        """CSVファイルをパースしてHardnessRowのリストを返す"""
        rows = []
        parent_folder = os.path.basename(os.path.dirname(file_path))
        file_name = os.path.basename(file_path)

        with open(file_path, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)

            # 1行目～10行目 から属性情報を取得
            set_device_name = cls.extract_device(next(reader))
            set_memory = cls.extract_numeric_value(next(reader))
            next(reader)  # skip Latitude
            next(reader)  # skip Longitude
            set_depth = cls.extract_numeric_value(next(reader))
            set_datetime = cls.extract_datetime(next(reader))
            set_spring = cls.extract_numeric_value(next(reader))
            set_cone = cls.extract_numeric_value(next(reader))
            next(reader)  # skip blank line
            next(reader)  # skip header line

            # 11行目以降のデータをパース
            for row in reader:
                rows.append(
                    HardnessRow(
                        set_device_name=set_device_name,
                        set_memory=set_memory,
                        set_datetime=set_datetime,
                        set_depth=set_depth,
                        set_spring=set_spring,
                        set_cone=set_cone,
                        depth=int(row[0]),
                        pressure=int(row[1]),
                        folder=parent_folder,
                        file_name=file_name,
                    )
                )
        return rows

    @classmethod
    def save_import_data(cls, rows: List[HardnessRow]) -> Dict[str, int]:
        """パース済みデータをデータベースに保存する"""
        created_count = 0
        m_device = {device.name: device for device in Device.objects.all()}

        for row in rows:
            try:
                device = m_device.get(row.set_device_name)
                if not device:
                    raise ValueError(f"Device not found: {row.set_device_name}")

                with transaction.atomic():
                    SoilHardnessMeasurement.objects.create(
                        set_device=device,
                        set_memory=row.set_memory,
                        set_datetime=row.set_datetime,
                        set_depth=row.set_depth,
                        set_spring=row.set_spring,
                        set_cone=row.set_cone,
                        depth=row.depth,
                        pressure=row.pressure,
                        folder=row.folder,
                    )
                    created_count += 1
            except IntegrityError as e:
                if "duplicate entry" in str(e).lower():
                    SoilHardnessMeasurementImportErrors.objects.create(
                        file=row.file_name,
                        folder=row.folder,
                        message="取り込み済み",
                    )
                else:
                    raise e
            except Exception as e:
                SoilHardnessMeasurementImportErrors.objects.create(
                    file=row.file_name,
                    folder=row.folder,
                    message=str(e),
                )

        return {"created": created_count}

    @staticmethod
    def get_suitable_ledgers(folder_name: str) -> List[LandLedger]:
        """フォルダ名に基づいて適切な帳簿を取得（使用済み帳簿は除外）"""
        # 既に硬度データに関連付けられた帳簿のIDを取得
        used_ledger_ids = (
            SoilHardnessMeasurement.objects.filter(land_ledger__isnull=False)
            .values_list("land_ledger_id", flat=True)
            .distinct()
        )

        # 基本クエリ：使用済み帳簿を除外
        base_query = LandLedger.objects.exclude(id__in=used_ledger_ids)

        # フォルダ名による絞り込み
        if folder_name:
            # フォルダ名に含まれるキーワードで圃場を検索
            lands = Land.objects.filter(name__icontains=folder_name.split("_")[0])
            if lands.exists():
                company = lands.first().company
                return list(base_query.filter(land__company=company).distinct())

        # 該当なしの場合は未使用の全帳簿を返す
        return list(base_query.order_by("pk"))

    @staticmethod
    def get_folder_groups_for_association() -> List[Dict[str, Any]]:
        """関連付け用のフォルダグループを取得"""
        # フォルダ単位でグループ化されたデータを取得
        folder_groups = (
            SoilHardnessMeasurement.objects.filter(land_block__isnull=True)
            .values("folder")
            .distinct()
        )

        result = []
        for folder_group in folder_groups:
            folder_name = folder_group["folder"]

            # 該当フォルダのレコード数を取得
            total_count = SoilHardnessMeasurement.objects.filter(
                folder=folder_name, land_block__isnull=True
            ).count()

            # 代表データとして最初の1レコードのみを取得
            representative_measurement = (
                SoilHardnessMeasurement.objects.filter(
                    folder=folder_name, land_block__isnull=True
                )
                .order_by("set_memory", "depth")
                .first()
            )

            if representative_measurement:
                # メモリー番号の範囲を計算
                memory_numbers = list(
                    SoilHardnessMeasurement.objects.filter(
                        folder=folder_name, land_block__isnull=True
                    )
                    .values_list("set_memory", flat=True)
                    .distinct()
                )
                min_memory = (
                    min(memory_numbers)
                    if memory_numbers
                    else representative_measurement.set_memory
                )
                max_memory = (
                    max(memory_numbers)
                    if memory_numbers
                    else representative_measurement.set_memory
                )

                group = {
                    "memory_anchor": representative_measurement.set_memory,
                    "measurements": [representative_measurement],
                    "folder_name": folder_name,
                    "count": total_count,
                    "min_memory": min_memory,
                    "max_memory": max_memory,
                }
                result.append(group)

        return result

    @staticmethod
    def get_total_groups_count() -> int:
        """総フォルダグループ数を取得"""
        return SoilHardnessMeasurement.objects.values("folder").distinct().count()

    @staticmethod
    def get_processed_groups_count() -> int:
        """処理済みフォルダグループ数を取得"""
        return (
            SoilHardnessMeasurement.objects.filter(land_ledger__isnull=False)
            .values("folder")
            .distinct()
            .count()
        )

    @classmethod
    def associate_with_ledger(cls, folder_name: str, land_ledger_id: int) -> bool:
        """フォルダ内のデータを指定された帳簿に紐付ける"""
        land_ledger = LandLedger.objects.filter(pk=land_ledger_id).first()
        if not land_ledger:
            return False

        # 処理対象のフォルダのデータを取得
        hardness_measurements = SoilHardnessMeasurement.objects.filter(
            folder=folder_name
        ).order_by("set_memory", "depth")

        if not hardness_measurements.exists():
            return False

        land_block_orders = SamplingOrder.objects.filter(
            sampling_method=land_ledger.sampling_method
        ).order_by("ordering")

        # 1つのland_blockあたりのレコード数を計算（深度×採取回数）
        max_depth = max(m.set_depth for m in hardness_measurements)
        records_per_block = max_depth * cls.SAMPLING_TIMES_PER_BLOCK

        needle = 0
        land_block_count = land_block_orders.count()
        current_time = timezone.now()

        for i, hardness_measurement in enumerate(hardness_measurements):
            if needle < land_block_count:
                hardness_measurement.land_block = land_block_orders[needle].land_block
            hardness_measurement.land_ledger = land_ledger
            hardness_measurement.updated_at = current_time

            if (i + 1) % records_per_block == 0:
                needle += 1

        SoilHardnessMeasurement.objects.bulk_update(
            list(hardness_measurements),
            fields=["land_block", "land_ledger", "updated_at"],
        )
        return True
