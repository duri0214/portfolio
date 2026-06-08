from soil_analysis.models import SoilChemicalMeasurementImportErrors


class ChemicalImportErrorRepository:
    """
    SoilChemicalMeasurementImportErrors関連のデータアクセスを担当するRepository
    """

    @staticmethod
    def create(
        row_number: int | None,
        land_name: str | None,
        message: str,
        remark: str | None = None,
    ) -> SoilChemicalMeasurementImportErrors:
        """
        インポートエラーを記録します

        Args:
            row_number: 行番号
            land_name: 圃場名
            message: エラーメッセージ
            remark: 備考

        Returns:
            SoilChemicalMeasurementImportErrors: 作成されたエラーインスタンス
        """
        return SoilChemicalMeasurementImportErrors.objects.create(
            row_number=row_number,
            land_name=land_name,
            message=message,
            remark=remark,
        )

    @staticmethod
    def delete_all() -> None:
        """
        全てのインポートエラーを削除します
        """
        SoilChemicalMeasurementImportErrors.objects.all().delete()

    @staticmethod
    def get_all() -> list[SoilChemicalMeasurementImportErrors]:
        """
        全てのインポートエラーを取得します

        Returns:
            list[SoilChemicalMeasurementImportErrors]: エラーリスト
        """
        return list(SoilChemicalMeasurementImportErrors.objects.all().order_by("id"))
