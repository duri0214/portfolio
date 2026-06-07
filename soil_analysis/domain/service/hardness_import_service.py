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
from soil_analysis.domain.valueobject.management.hardness_import_parser import (
    HardnessImportParser,
    HardnessRow,
    HardnessParseResult,
)
from soil_analysis.models import (
    SoilHardnessMeasurement,
    LandLedger,
)


class HardnessImportService:
    SAMPLING_TIMES_PER_BLOCK = 5

    @classmethod
    def parse_csv(cls, file_path: str) -> HardnessParseResult:
        """
        CSVファイルをパースしてHardnessParseResultを返す

        Args:
            file_path: CSVファイルのパス

        Returns:
            HardnessParseResult: パースされたデータの結果
        """
        return HardnessImportParser.parse_csv(file_path)

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
            except IntegrityError:
                HardnessImportErrorRepository.create(
                    file=row.file_name,
                    folder=row.folder,
                    message="取り込み済み",
                )
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
