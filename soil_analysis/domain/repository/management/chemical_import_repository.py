from django.db import transaction

from soil_analysis.domain.repository.chemical_import_error import (
    ChemicalImportErrorRepository,
)
from soil_analysis.models import (
    LandLedger,
    SoilChemicalMeasurement,
)


class ChemicalImportRepository:
    """
    化学分析データの永続化を担当するリポジトリ
    """

    @classmethod
    def exists_ledger(cls, land_ledger_id: int) -> bool:
        """
        指定された LandLedger が存在するか確認する
        """
        return LandLedger.objects.filter(id=land_ledger_id).exists()

    @classmethod
    def delete_all_errors(cls):
        """
        すべてのインポートエラーを削除する
        """
        ChemicalImportErrorRepository.delete_all()

    @classmethod
    def create_error(
        cls,
        row_number: int | None,
        land_name: str | None,
        message: str,
        remark: str | None = None,
    ):
        """
        インポートエラーを記録する
        """
        ChemicalImportErrorRepository.create(
            row_number=row_number,
            land_name=land_name,
            message=message,
            remark=remark,
        )

    @classmethod
    def save_measurements(
        cls, measurements_data: list[dict], source_file: str | None = None
    ) -> dict[str, int]:
        """
        化学分析データを保存する。既存データがある場合は更新する。

        Args:
            measurements_data: 保存するデータのリスト。各要素は 'land_ledger_id' と 'record_values' を含む
            source_file: データ元ファイル名

        Returns:
            作成/更新件数
        """
        try:
            created_count = 0
            updated_count = 0

            ledger_ids = [d["land_ledger_id"] for d in measurements_data]
            existing_analyses = SoilChemicalMeasurement.objects.filter(
                land_ledger_id__in=ledger_ids
            )
            existing_map = {m.land_ledger_id: m for m in existing_analyses}

            to_create = []
            to_update = []

            with transaction.atomic():
                for data in measurements_data:
                    ledger_id = data["land_ledger_id"]
                    record_values = data["record_values"]
                    existing = existing_map.get(ledger_id)

                    if existing:
                        for field_name, field_value in record_values.items():
                            setattr(existing, field_name, field_value)
                        if source_file:
                            existing.source_file = source_file
                        to_update.append(existing)
                        updated_count += 1
                    else:
                        new_record = SoilChemicalMeasurement(
                            land_ledger_id=ledger_id,
                            source_file=source_file,
                            **record_values,
                        )
                        to_create.append(new_record)
                        created_count += 1

                if to_create:
                    SoilChemicalMeasurement.objects.bulk_create(to_create)
                if to_update:
                    update_fields = list(measurements_data[0]["record_values"].keys())
                    if source_file:
                        update_fields.append("source_file")
                    SoilChemicalMeasurement.objects.bulk_update(
                        to_update, update_fields
                    )

            return {"created": created_count, "updated": updated_count}
        except Exception as e:
            cls.create_error(
                row_number=None,
                land_name=None,
                message=f"保存中にエラーが発生しました: {str(e)}",
                remark=f"source_file: {source_file}" if source_file else None,
            )
            raise e
