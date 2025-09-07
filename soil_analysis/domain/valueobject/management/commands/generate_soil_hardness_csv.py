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
        base_pressure: 基本圧力値（表層の硬度）
        max_pressure_increase: 最大増加量（深度MAX_DEPTHでの増加量）
        noise_range: ランダム変動範囲のタプル (min, max)、マイナス値も含む
        last_pressure: 前回の圧力値（連続性維持用）
    """

    # 土壌の物理特性に関する定数
    MAX_PRESSURE_DELTA = 100

    # 毎回ランダム値を生成するにはdefault_factory関数を使用
    base_pressure: int = field(default_factory=lambda: random.randint(232, 350))
    max_pressure_increase: int = field(default_factory=lambda: 2000)
    noise_range: tuple[int, int] = field(default_factory=lambda: (-200, 200))
    last_pressure: int | None = None

    def __post_init__(self):
        """初期化後に実行される処理"""
        # 初期値設定
        self.last_pressure = self.base_pressure

    def calculate_pressure(self, depth: int) -> int:
        """深度に応じた圧力値を計算する

        数学関数式: P(d) = P₀ + k × (d/d_max)² + noise
        P₀: 基本圧力値, d: 深度, d_max: 最大深度, k: 最大増加圧力

        Args:
            depth: 深度 (1-60cm)

        Returns:
            int: 計算された圧力値
        """
        # 2次関数モデルによる圧力計算
        depth_ratio = depth / SoilHardnessDevice.MAX_DEPTH  # 0～1の比率
        quadratic_factor = depth_ratio**2  # 2次関数的な増加

        # 基本圧力に2次関数的な増加を加える
        depth_pressure = self.base_pressure + (
            quadratic_factor * self.max_pressure_increase
        )

        # ランダム変動の追加
        min_noise, max_noise = self.noise_range
        noise = random.randint(min_noise, max_noise)

        # 圧力値計算
        calculated_pressure = int(depth_pressure) + noise

        # 前回値との連続性を確保（急激な変化を抑制）
        if self.last_pressure is not None:
            delta = calculated_pressure - self.last_pressure

            if delta > self.MAX_PRESSURE_DELTA:
                calculated_pressure = self.last_pressure + self.MAX_PRESSURE_DELTA

        # 有効範囲内に収める
        pressure = max(232, min(3000, calculated_pressure))

        # 次回のために今回の値を保存
        self.last_pressure = pressure

        return pressure


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
