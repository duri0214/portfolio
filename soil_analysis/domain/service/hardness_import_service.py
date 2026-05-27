import csv
import dataclasses
import os
from datetime import datetime

import pytz
from django.db import transaction, IntegrityError
from django.utils import timezone

from soil_analysis.domain.repository.device import DeviceRepository
from soil_analysis.domain.repository.hardness_import_error import (
    HardnessImportErrorRepository,
)
from soil_analysis.domain.repository.hardness_measurement import (
    SoilHardnessMeasurementRepository,
)
from soil_analysis.domain.repository.sampling_order import SamplingOrderRepository
from soil_analysis.models import (
    SoilHardnessMeasurement,
    LandLedger,
)


@dataclasses.dataclass(frozen=True)
class HardnessRow:
    """
    土壌硬度データをパースしたデータ行

    Attributes:
        set_device_name: デバイス名
        set_memory: メモリー番号
        set_datetime: 測定日時
        set_depth: 設定深度
        set_spring: スプリング番号
        set_cone: コーン番号
        depth: 測定深度
        pressure: 圧力
        folder: フォルダ名
        file_name: ファイル名
    """

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
    def parse_csv(cls, file_path: str) -> list[HardnessRow]:
        """
        CSVファイルをパースしてHardnessRowのリストを返す

        Args:
            file_path: CSVファイルのパス

        Returns:
            list[HardnessRow]: パースされたデータのリスト
        """
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
    def save_import_data(cls, rows: list[HardnessRow]) -> dict[str, int]:
        """
        パース済みデータをデータベースに保存する

        Args:
            rows: 保存するデータのリスト

        Returns:
            dict[str, int]: 作成されたレコード数などの情報
        """
        created_count = 0
        # デバイス情報を一括取得してキャッシュ
        m_device = {device.name: device for device in DeviceRepository.get_all()}

        for row in rows:
            try:
                device = m_device.get(row.set_device_name)
                if not device:
                    # デバイスが存在しない場合は作成
                    device = DeviceRepository.get_or_create_by_name(row.set_device_name)
                    m_device[row.set_device_name] = device

                with transaction.atomic():
                    measurement = SoilHardnessMeasurement(
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
                    SoilHardnessMeasurementRepository.create(measurement)
                    created_count += 1
            except IntegrityError as e:
                if "duplicate entry" in str(e).lower():
                    HardnessImportErrorRepository.create(
                        file=row.file_name,
                        folder=row.folder,
                        message="取り込み済み",
                    )
                else:
                    raise e
            except Exception as e:
                HardnessImportErrorRepository.create(
                    file=row.file_name,
                    folder=row.folder,
                    message=str(e),
                )

        return {"created": created_count}

    @staticmethod
    def get_suitable_ledgers(folder_name: str) -> list[LandLedger]:
        """
        フォルダ名に基づいて適切な帳簿を取得（使用済み帳簿は除外）

        Args:
            folder_name: フォルダ名

        Returns:
            list[LandLedger]: 適合する帳簿のリスト
        """
        return SoilHardnessMeasurementRepository.get_suitable_ledgers(folder_name)

    @staticmethod
    def get_folder_groups_for_association() -> list[dict]:
        """
        関連付け用のフォルダグループを取得

        Returns:
            list[dict]: フォルダグループ情報のリスト
        """
        return SoilHardnessMeasurementRepository.get_folder_groups_for_association()

    @staticmethod
    def get_total_groups_count() -> int:
        """
        総フォルダグループ数を取得

        Returns:
            int: 総グループ数
        """
        return SoilHardnessMeasurementRepository.get_total_groups_count()

    @staticmethod
    def get_processed_groups_count() -> int:
        """
        処理済みフォルダグループ数を取得

        Returns:
            int: 処理済みグループ数
        """
        return SoilHardnessMeasurementRepository.get_processed_groups_count()

    @classmethod
    def associate_with_ledger(cls, folder_name: str, land_ledger_id: int) -> bool:
        """
        フォルダ内のデータを指定された帳簿に紐付ける

        Args:
            folder_name: フォルダ名
            land_ledger_id: 帳簿のID

        Returns:
            bool: 成功した場合はTrue、失敗した場合はFalse
        """
        # 帳簿の取得はLandLedgerRepositoryがあるならそれを使うべきだが、
        # ここではモデル直接参照を避け、将来的にRepositoryに移行することを検討
        # 現状は簡易的にモデルフィルタリングを使用
        land_ledger = LandLedger.objects.filter(pk=land_ledger_id).first()
        if not land_ledger:
            return False

        # 処理対象のフォルダのデータを取得
        hardness_measurements = SoilHardnessMeasurementRepository.get_all_by_folder(
            folder_name
        )

        if not hardness_measurements:
            return False

        land_block_orders = SamplingOrderRepository.get_by_sampling_method(
            land_ledger.sampling_method_id
        )

        # 1つのland_blockあたりのレコード数を計算（深度×採取回数）
        max_depth = max(m.set_depth for m in hardness_measurements)
        records_per_block = max_depth * cls.SAMPLING_TIMES_PER_BLOCK

        needle = 0
        land_block_count = len(land_block_orders)
        current_time = timezone.now()

        for i, hardness_measurement in enumerate(hardness_measurements):
            if needle < land_block_count:
                hardness_measurement.land_block = land_block_orders[needle].land_block
            hardness_measurement.land_ledger = land_ledger
            hardness_measurement.updated_at = current_time

            if (i + 1) % records_per_block == 0:
                needle += 1

        # ルール32, 34に従いRepository経由で一括更新
        SoilHardnessMeasurementRepository.bulk_update(
            hardness_measurements, fields=["land_block", "land_ledger", "updated_at"]
        )
        return True
