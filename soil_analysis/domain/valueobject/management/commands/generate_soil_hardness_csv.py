class SoilHardnessDevice:
    """土壌硬度計測器に関連する定数と仕様"""

    DEVICE_NAME = "DIK-5531"
    MAX_DEPTH = 60


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
        return [
            [SoilHardnessDevice.DEVICE_NAME, "Digital Cone Penetrometer"],
            ["Memory No.", str(memory_no).zfill(4)],
            ["Latitude", "N 00.00.0000"],
            ["Longitude", "E 000.00.0000"],
            ["Set Depth[cm]", str(SoilHardnessDevice.MAX_DEPTH)],
            ["Date and Time", date_str],
            ["Spring[N/48.5mm]", "490"],
            ["Cone[cm2]", "2"],
            [],
            ["Depth[cm]", "Pressure[kPa]", "DateTime", "GpsMode", "GPS Satellites"],
        ]
