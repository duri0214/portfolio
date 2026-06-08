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

    @staticmethod
    def validate_analysis_numbers(rows: list) -> list[str]:
        """
        分析番号の重複（DBおよびファイル内）をチェックします。

        Args:
            rows: パースされた行データのリスト（analysis_number, row_number を持つこと）

        Returns:
            エラーメッセージのリスト
        """
        errors = []
        seen_analysis_numbers = set()
        existing_numbers = set(
            SoilChemicalMeasurement.objects.exclude(
                analysis_number__isnull=True
            ).values_list("analysis_number", flat=True)
        )

        for row in rows:
            num = row.analysis_number
            if num is None:
                continue

            if num in seen_analysis_numbers:
                errors.append(
                    f"row={row.row_number}: 分析番号 {num} がファイル内で重複しています。"
                )
            elif num in existing_numbers:
                errors.append(
                    f"row={row.row_number}: 分析番号 {num} は既に取り込まれています。"
                )
            seen_analysis_numbers.add(num)

        return errors
