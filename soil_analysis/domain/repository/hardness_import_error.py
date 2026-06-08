from soil_analysis.models import SoilHardnessMeasurementImportErrors


class HardnessImportErrorRepository:
    """
    SoilHardnessMeasurementImportErrors関連のデータアクセスを担当するRepository
    """

    @staticmethod
    def create(
        file: str, folder: str, message: str
    ) -> SoilHardnessMeasurementImportErrors:
        """
        インポートエラーを記録します

        Args:
            file: ファイル名
            folder: フォルダ名
            message: エラーメッセージ

        Returns:
            SoilHardnessMeasurementImportErrors: 作成されたエラーインスタンス
        """
        return SoilHardnessMeasurementImportErrors.objects.create(
            file=file, folder=folder, message=message
        )

    @staticmethod
    def delete_all() -> None:
        """
        全てのインポートエラーを削除します
        """
        SoilHardnessMeasurementImportErrors.objects.all().delete()

    @staticmethod
    def get_all() -> list[SoilHardnessMeasurementImportErrors]:
        """
        全てのインポートエラーを取得します

        Returns:
            list[SoilHardnessMeasurementImportErrors]: エラーリスト
        """
        return list(SoilHardnessMeasurementImportErrors.objects.all().order_by("id"))
