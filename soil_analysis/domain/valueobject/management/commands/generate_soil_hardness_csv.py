import random
from dataclasses import dataclass, field


class SoilHardnessDevice:
    """土壌硬度計測器に関連する定数と仕様"""

    DEVICE_NAME = "DIK-5531"
    MAX_DEPTH = 60


@dataclass
class SoilHardnessCharacteristics:
    """土壌特性を表すValueObject

    パラメータを指定しない場合は自動的にランダム値が使用されます。

    Attributes:
        base_pressure: 基本圧力値
        depth_factor: 深度による増加係数
        noise_range: 変動範囲のタプル (min, max)
    """

    # 毎回ランダム値を生成するにはdefault_factory関数を使用
    base_pressure: int = field(default_factory=lambda: random.randint(232, 350))
    depth_factor: int = field(default_factory=lambda: random.randint(8, 15))
    noise_range: tuple[int, int] = field(default_factory=lambda: (-100, 100))


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
