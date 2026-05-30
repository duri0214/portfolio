import dataclasses


@dataclasses.dataclass(frozen=True)
class HardnessBlockAssessment:
    """
    1ブロック分の硬度集計結果を保持するValue Object。

    Attributes:
        block_name: ブロック名（A1, B2など）
        avg_pressure: 平均圧力（kPa）
        depth_pressures: 深度ごとの平均圧力リスト [(depth, pressure), ...]
    """

    block_name: str
    avg_pressure: float | None
    # 深度ごとの平均圧力リスト [(depth, pressure), ...]
    depth_pressures: list[tuple[int, float]] = dataclasses.field(default_factory=list)

    # しきい値の定数（kPa）
    THRESHOLD_LOW = 1500.0
    THRESHOLD_HIGH = 2500.0
    MAX_SCALE = 4000.0

    @property
    def display_value(self) -> str:
        if self.avg_pressure is None:
            return "-"
        return f"{self.avg_pressure:,.0f}"

    @property
    def sparkline_points(self) -> str:
        """
        SVGのpolyline用のポイント文字列を生成する。
        x: 0-100 (深度 0-60cm を想定)
        y: 0-100 (圧力 0-MAX_SCALE を反転)
        """
        if not self.depth_pressures:
            return ""

        max_depth = 60.0
        points = []
        for depth, pressure in self.depth_pressures:
            x = (depth / max_depth) * 100.0
            y = 100.0 - min(100.0, (pressure / self.MAX_SCALE) * 100.0)
            points.append(f"{x:.1f},{y:.1f}")
        return " ".join(points)

    @property
    def assessment_category(self) -> str:
        """
        しきい値に基づいた判定カテゴリを返す。
        """
        if self.avg_pressure is None:
            return "none"
        if self.avg_pressure <= self.THRESHOLD_LOW:
            return "good"
        if self.avg_pressure <= self.THRESHOLD_HIGH:
            return "warning"
        return "bad"


@dataclasses.dataclass(frozen=True)
class HardnessAssessmentVO:
    """
    圃場全体の硬度集計結果（9ブロック分）を保持するValue Object。

    Attributes:
        block_assessments: ブロック名をキーとする HardnessBlockAssessment の辞書
    """

    block_assessments: dict[str, HardnessBlockAssessment]

    @classmethod
    def from_measurements(
        cls,
        measurements_by_block: dict[str, float | None],
        depth_data_by_block: dict[str, list[tuple[int, float]]],
    ):
        assessments = {
            name: HardnessBlockAssessment(
                block_name=name,
                avg_pressure=avg,
                depth_pressures=depth_data_by_block.get(name, []),
            )
            for name, avg in measurements_by_block.items()
        }
        return cls(block_assessments=assessments)

    def get_block(self, block_name: str) -> HardnessBlockAssessment | None:
        return self.block_assessments.get(block_name)
