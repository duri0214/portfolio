from soil_analysis.models import SoilChemicalMeasurement, LandLedger


class SoilChemicalMeasurementRepository:
    """
    SoilChemicalMeasurement関連のデータアクセスを担当するRepository
    """

    @staticmethod
    def get_by_ledger(land_ledger: LandLedger) -> SoilChemicalMeasurement | None:
        """
        帳簿に紐づく化学分析データを取得します

        Args:
            land_ledger: 帳簿インスタンス

        Returns:
            SoilChemicalMeasurement | None: 化学分析データ。存在しない場合はNone
        """
        return SoilChemicalMeasurement.objects.filter(land_ledger=land_ledger).first()
