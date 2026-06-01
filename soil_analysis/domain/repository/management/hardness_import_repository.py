from django.db import transaction, IntegrityError

from soil_analysis.domain.repository.device import DeviceRepository
from soil_analysis.domain.repository.hardness_import_error import (
    HardnessImportErrorRepository,
)
from soil_analysis.domain.repository.hardness_measurement import (
    SoilHardnessMeasurementRepository,
)
from soil_analysis.models import SoilHardnessMeasurement


class HardnessImportRepository:
    """
    土壌硬度データの永続化を担当するリポジトリ
    """

    @classmethod
    def delete_all_errors(cls):
        """
        すべてのインポートエラーを削除する
        """
        HardnessImportErrorRepository.delete_all()

    @classmethod
    def create_error(cls, file: str, folder: str, message: str):
        """
        インポートエラーを記録する
        """
        HardnessImportErrorRepository.create(file=file, folder=folder, message=message)

    @classmethod
    def save_measurement(cls, row_data) -> bool:
        """
        土壌硬度データを保存する

        Args:
            row_data: HardnessRow オブジェクト

        Returns:
            bool: 成功した場合は True
        """
        try:
            device = DeviceRepository.get_or_create_by_name(row_data.set_device_name)

            with transaction.atomic():
                measurement = SoilHardnessMeasurement(
                    set_device=device,
                    set_memory=row_data.set_memory,
                    set_datetime=row_data.set_datetime,
                    set_depth=row_data.set_depth,
                    set_spring=row_data.set_spring,
                    set_cone=row_data.set_cone,
                    depth=row_data.depth,
                    pressure=row_data.pressure,
                    folder=row_data.folder,
                )
                SoilHardnessMeasurementRepository.create(measurement)
                return True
        except IntegrityError as e:
            if "duplicate entry" in str(e).lower():
                cls.create_error(
                    file=row_data.file_name,
                    folder=row_data.folder,
                    message="取り込み済み",
                )
                return False
            else:
                raise e
        except Exception as e:
            cls.create_error(
                file=row_data.file_name,
                folder=row_data.folder,
                message=str(e),
            )
            raise e
