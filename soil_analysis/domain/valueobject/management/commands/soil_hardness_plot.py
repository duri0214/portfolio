from datetime import date

FILENAME_PATTERN = "soil_hardness_land_ledger_id_{land_ledger_id}_{date}_3d_surface.png"


class SoilHardnessPlotName:
    """土壌硬度3Dプロットの命名規約ヘルパ

    このクラスの目的は、ファイル名生成ロジックを一元化して開発者の修正漏れを防ぐこと。
    ファイル名を生成する際は必ずこのクラスのメソッドを使用すること
    """

    @staticmethod
    def build_filename(land_ledger_id: int, sampling_date: date) -> str:
        """土壌硬度プロット画像のファイル名を生成する

        このメソッドがファイル名を生成します。
        他の場所で独自にファイル名を生成しないでください。

        Args:
            land_ledger_id: 圃場帳簿ID
            sampling_date: サンプリング日

        Returns:
            str: 生成されたファイル名 (例: soil_hardness_land_ledger_id_123_20240705_3d_surface.png)
        """
        ymd = sampling_date.strftime("%Y%m%d")
        return FILENAME_PATTERN.format(land_ledger_id=land_ledger_id, date=ymd)
