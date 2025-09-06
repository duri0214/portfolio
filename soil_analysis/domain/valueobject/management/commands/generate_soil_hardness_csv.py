from dataclasses import dataclass


class SoilHardnessDevice:
    """土壌硬度計測器に関連する定数と仕様"""

    # デバイスの仕様値
    DEVICE_NAME = "DIK-5531"
    MAX_DEPTH = 60


@dataclass
class CsvHeaderItem:
    """CSVヘッダー項目を表すValueObject"""

    key: str
    value: str

    def to_row(self) -> list[str]:
        """CSVの行形式に変換"""
        return [self.key, self.value, "", "", ""]


class SoilHardnessCsvHeader:
    """土壌硬度計CSV形式のヘッダーを管理するクラス"""

    @classmethod
    def create_header_rows(cls, memory_no: int, date_str: str) -> list[list[str]]:
        """CSVヘッダー行のリストを生成する

        Args:
            memory_no: メモリ番号
            date_str: 日時文字列

        Returns:
            List[List[str]]: CSVヘッダー行のリスト
        """
        headers = [
            CsvHeaderItem(SoilHardnessDevice.DEVICE_NAME, "Digital Cone Penetrometer"),
            CsvHeaderItem("Memory No.", str(memory_no)),
            CsvHeaderItem("Latitude", "N 00.00.0000"),
            CsvHeaderItem("Longitude", "E 000.00.0000"),
            CsvHeaderItem("Set Depth[cm]", str(SoilHardnessDevice.MAX_DEPTH)),
            CsvHeaderItem("Date and Time", date_str),
            CsvHeaderItem("Spring[N/48.5mm]", "490"),
            CsvHeaderItem("Cone[cm2]", "2"),
        ]

        # ヘッダー行に変換
        result = [item.to_row() for item in headers]
        # 空行を追加
        result.append(["", "", "", "", ""])
        # データヘッダー行を追加
        result.append(
            ["Depth[cm]", "Pressure[kPa]", "DateTime", "GpsMode", "GPS Satellites"]
        )

        return result
