from dataclasses import dataclass


class SoilHardnessDevice:
    """土壌硬度計測器に関連する定数と仕様"""

    # デバイスの仕様値
    SPRING_VALUE = 490
    CONE_VALUE = 2.0
    DEVICE_TYPE = "Digital Cone Penetrometer"
    DEFAULT_DEVICE_NAME = "DIK-5531"

    # GPS情報
    GPS_MODE = 0
    GPS_SATELLITES = 0

    # GPS座標形式
    GPS_COORD_FILENAME = ("N00000000", "E000000000")  # ファイル名用
    GPS_COORD_CSV = ("N 00.00.0000", "E 000.00.0000")  # CSV内表示用

    # ファイル関連
    CSV_DIR_NAME = "取り込みCSV"
    DEFAULT_ZIP_FILENAME = "取り込みCSV.zip"


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
    def create_header_rows(
        cls, device_name: str, memory_no: int, max_depth: int, date_str: str
    ) -> list[list[str]]:
        """CSVヘッダー行のリストを生成する

        Args:
            device_name: 計測器名
            memory_no: メモリ番号
            max_depth: 最大深度
            date_str: 日時文字列

        Returns:
            List[List[str]]: CSVヘッダー行のリスト
        """
        # 緯度経度は常に固定値を使用
        lat_str, lng_str = SoilHardnessDevice.GPS_COORD_CSV

        headers = [
            CsvHeaderItem(device_name, SoilHardnessDevice.DEVICE_TYPE),
            CsvHeaderItem("Memory No.", str(memory_no)),
            CsvHeaderItem("Latitude", lat_str),
            CsvHeaderItem("Longitude", lng_str),
            CsvHeaderItem("Set Depth[cm]", str(max_depth)),
            CsvHeaderItem("Date and Time", date_str),
            CsvHeaderItem("Spring[N/48.5mm]", str(SoilHardnessDevice.SPRING_VALUE)),
            CsvHeaderItem("Cone[cm2]", str(SoilHardnessDevice.CONE_VALUE)),
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
