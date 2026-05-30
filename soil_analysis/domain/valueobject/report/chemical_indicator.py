from dataclasses import dataclass

from .fields import REPORT_FIELD_BY_KEY


def _get_item_name(key: str) -> str:
    """REPORT_FIELD_BY_KEYから項目名を表示形式 label(description) で取得する"""
    field = REPORT_FIELD_BY_KEY.get(key)
    if not field:
        return key
    return f"{field.label}({field.description})"


@dataclass(frozen=True)
class ItemAssessment:
    """
    各項目の判定結果

    Attributes:
        name: 項目名 (例: "pH(水素イオン濃度)")
        value: 測定値。欠損時は None
        label: 判定ラベル ("低", "適正", "高", "過剰", "不明")
        comment: 判定コメント
        level: 表示レベル ("success", "warning", "danger", "info", "secondary")
        min_threshold: 判定に使用した下限閾値
        max_threshold: 判定に使用した上限閾値
    """

    name: str
    value: float | None
    label: str
    comment: str
    level: str
    min_threshold: float | None = None
    max_threshold: float | None = None

    @property
    def threshold_statement(self) -> str:
        """判定基準のテキスト表現"""
        if self.min_threshold is not None and self.max_threshold is not None:
            return f"適正しきい値は{self.min_threshold}〜{self.max_threshold}の範囲"
        if self.min_threshold is not None:
            return f"適正しきい値は{self.min_threshold}以上"
        if self.max_threshold is not None:
            return f"適正しきい値は{self.max_threshold}以下"
        return "-"


@dataclass(frozen=True)
class PhVO:
    value: float | None
    LOW = 6.0
    HIGH = 7.0

    def is_low(self) -> bool:
        return self.value is not None and self.value < self.LOW

    def is_high(self) -> bool:
        return self.value is not None and self.value > self.HIGH

    def assess(self) -> ItemAssessment:
        name = _get_item_name("ph")
        if self.value is None:
            return ItemAssessment(
                name,
                None,
                "不明",
                "データがありません",
                "secondary",
                self.LOW,
                self.HIGH,
            )
        if self.is_low():
            return ItemAssessment(
                name, self.value, "低", "酸性傾向です", "warning", self.LOW, self.HIGH
            )
        if self.is_high():
            return ItemAssessment(
                name,
                self.value,
                "高",
                "アルカリ性傾向です",
                "warning",
                self.LOW,
                self.HIGH,
            )
        return ItemAssessment(
            name, self.value, "適正", "適正範囲内です", "success", self.LOW, self.HIGH
        )


@dataclass(frozen=True)
class EcVO:
    value: float | None
    LOW = 0.1
    HIGH = 0.5

    def is_low(self) -> bool:
        return self.value is not None and self.value < self.LOW

    def is_high(self) -> bool:
        return self.value is not None and self.value > self.HIGH

    def assess(self) -> ItemAssessment:
        name = _get_item_name("ec")
        if self.value is None:
            return ItemAssessment(
                name,
                None,
                "不明",
                "データがありません",
                "secondary",
                self.LOW,
                self.HIGH,
            )
        if self.is_low():
            return ItemAssessment(
                name,
                self.value,
                "低",
                "肥切れの可能性があります",
                "warning",
                self.LOW,
                self.HIGH,
            )
        if self.is_high():
            return ItemAssessment(
                name,
                self.value,
                "過剰",
                "肥料過多の可能性があります",
                "danger",
                self.LOW,
                self.HIGH,
            )
        return ItemAssessment(
            name, self.value, "適正", "適正範囲内です", "success", self.LOW, self.HIGH
        )


@dataclass(frozen=True)
class Nh4nVO:
    value: float | None
    UPPER_LIMIT = 5.0

    def is_high(self) -> bool:
        return self.value is not None and self.value > self.UPPER_LIMIT

    def assess(self) -> ItemAssessment:
        name = _get_item_name("nh4n")
        if self.value is None:
            return ItemAssessment(
                name,
                None,
                "不明",
                "データがありません",
                "secondary",
                None,
                self.UPPER_LIMIT,
            )
        if self.is_high():
            return ItemAssessment(
                name,
                self.value,
                "過剰",
                "アンモニア態窒素が過剰です",
                "danger",
                None,
                self.UPPER_LIMIT,
            )
        return ItemAssessment(
            name,
            self.value,
            "適正",
            "適正範囲内です",
            "success",
            None,
            self.UPPER_LIMIT,
        )


@dataclass(frozen=True)
class No3nVO:
    value: float | None
    UPPER_LIMIT = 15.0

    def is_high(self) -> bool:
        return self.value is not None and self.value > self.UPPER_LIMIT

    def assess(self) -> ItemAssessment:
        name = _get_item_name("no3n")
        if self.value is None:
            return ItemAssessment(
                name,
                None,
                "不明",
                "データがありません",
                "secondary",
                None,
                self.UPPER_LIMIT,
            )
        if self.is_high():
            return ItemAssessment(
                name,
                self.value,
                "過剰",
                "硝酸態窒素が過剰です",
                "danger",
                None,
                self.UPPER_LIMIT,
            )
        return ItemAssessment(
            name,
            self.value,
            "適正",
            "適正範囲内です",
            "success",
            None,
            self.UPPER_LIMIT,
        )


@dataclass(frozen=True)
class CecVO:
    value: float | None
    LOW = 12.0

    def is_low(self) -> bool:
        return self.value is not None and self.value < self.LOW

    def assess(self) -> ItemAssessment:
        name = _get_item_name("cec")
        if self.value is None:
            return ItemAssessment(
                name, None, "不明", "データがありません", "secondary", self.LOW, None
            )
        if self.is_low():
            return ItemAssessment(
                name, self.value, "低", "保肥力が低いです", "warning", self.LOW, None
            )
        return ItemAssessment(
            name,
            self.value,
            "適正",
            "十分な保肥力があります",
            "success",
            self.LOW,
            None,
        )


@dataclass(frozen=True)
class BaseSaturationVO:
    value: float | None
    LOW = 60.0
    HIGH = 80.0
    OVER = 100.0

    def is_low(self) -> bool:
        return self.value is not None and self.value < self.LOW

    def is_high(self) -> bool:
        return self.value is not None and self.value > self.HIGH

    def is_over(self) -> bool:
        return self.value is not None and self.value > self.OVER

    def assess(self, cec: float | None = None) -> ItemAssessment:
        name = _get_item_name("base_saturation")

        # CECに応じた動的な閾値設定
        low_limit = self.LOW
        high_limit = self.HIGH
        if cec is not None:
            if cec >= 20.0:
                # CEC 20以上なら80%が目安
                high_limit = 80.0
            elif cec < 15.0:
                # CEC 15未満なら100%以上
                low_limit = 100.0

        if self.value is None:
            return ItemAssessment(
                name,
                None,
                "不明",
                "データがありません",
                "secondary",
                low_limit,
                high_limit,
            )
        if self.is_over():
            return ItemAssessment(
                name,
                self.value,
                "過剰",
                "塩基類が飽和状態を超えています。土が保持できる量を超えています。",
                "danger",
                low_limit,
                high_limit,
            )
        if self.value < low_limit:
            return ItemAssessment(
                name,
                self.value,
                "低",
                f"塩基類が不足しています（目標: {low_limit}%以上）",
                "warning",
                low_limit,
                high_limit,
            )
        if self.value > high_limit:
            return ItemAssessment(
                name,
                self.value,
                "過剰",
                f"塩基類が多めです（目標: {high_limit}%以下）",
                "danger",
                low_limit,
                high_limit,
            )
        return ItemAssessment(
            name, self.value, "適正", "適正範囲内です", "success", low_limit, high_limit
        )


@dataclass(frozen=True)
class P2o5VO:
    value: float | None
    LOW = 50.0
    HIGH = 100.0

    def is_low(self) -> bool:
        return self.value is not None and self.value < self.LOW

    def is_high(self) -> bool:
        return self.value is not None and self.value > self.HIGH

    def assess(self) -> ItemAssessment:
        name = _get_item_name("p2o5")
        if self.value is None:
            return ItemAssessment(
                name,
                None,
                "不明",
                "データがありません",
                "secondary",
                self.LOW,
                self.HIGH,
            )
        if self.is_low():
            return ItemAssessment(
                name,
                self.value,
                "低",
                "リン酸が不足しています。適正なリン酸施用が必要です。",
                "warning",
                self.LOW,
                self.HIGH,
            )
        if self.is_high():
            return ItemAssessment(
                name,
                self.value,
                "過剰",
                "リン酸が過剰です。根瘤病のリスクを高める可能性があります。",
                "danger",
                self.LOW,
                self.HIGH,
            )
        return ItemAssessment(
            name, self.value, "適正", "適正範囲内です", "success", self.LOW, self.HIGH
        )


@dataclass(frozen=True)
class HumusVO:
    value: float | None
    LOW = 3.0

    def is_low(self) -> bool:
        return self.value is not None and self.value < self.LOW

    def assess(self) -> ItemAssessment:
        name = _get_item_name("humus")
        if self.value is None:
            return ItemAssessment(
                name, None, "不明", "データがありません", "secondary", self.LOW, None
            )
        if self.is_low():
            return ItemAssessment(
                name, self.value, "低", "腐植が不足しています", "danger", self.LOW, None
            )
        return ItemAssessment(
            name, self.value, "適正", "適正範囲内です", "success", self.LOW, None
        )


@dataclass(frozen=True)
class CaoVO:
    value: float | None
    LOW = 300.0
    HIGH = 450.0

    def is_low(self) -> bool:
        return self.value is not None and self.value < self.LOW

    def is_high(self) -> bool:
        return self.value is not None and self.value > self.HIGH

    def assess(self) -> ItemAssessment:
        name = _get_item_name("cao")
        if self.value is None:
            return ItemAssessment(
                name,
                None,
                "不明",
                "データがありません",
                "secondary",
                self.LOW,
                self.HIGH,
            )
        if self.is_low():
            return ItemAssessment(
                name,
                self.value,
                "低",
                "石灰が不足しています",
                "warning",
                self.LOW,
                self.HIGH,
            )
        if self.is_high():
            return ItemAssessment(
                name,
                self.value,
                "過剰",
                "石灰が過剰です。他の成分（苦土・加里等）の吸収阻害を招く恐れがあります。",
                "danger",
                self.LOW,
                self.HIGH,
            )
        return ItemAssessment(
            name, self.value, "適正", "適正範囲内です", "success", self.LOW, self.HIGH
        )


@dataclass(frozen=True)
class MgoVO:
    value: float | None
    LOW = 30.0
    HIGH = 50.0

    def is_low(self) -> bool:
        return self.value is not None and self.value < self.LOW

    def is_high(self) -> bool:
        return self.value is not None and self.value > self.HIGH

    def assess(self) -> ItemAssessment:
        name = _get_item_name("mgo")
        if self.value is None:
            return ItemAssessment(
                name,
                None,
                "不明",
                "データがありません",
                "secondary",
                self.LOW,
                self.HIGH,
            )
        if self.is_low():
            return ItemAssessment(
                name,
                self.value,
                "低",
                "苦土が不足しています",
                "warning",
                self.LOW,
                self.HIGH,
            )
        if self.is_high():
            return ItemAssessment(
                name,
                self.value,
                "過剰",
                "苦土が過剰です",
                "danger",
                self.LOW,
                self.HIGH,
            )
        return ItemAssessment(
            name, self.value, "適正", "適正範囲内です", "success", self.LOW, self.HIGH
        )


@dataclass(frozen=True)
class K2oVO:
    value: float | None
    LOW = 20.0
    HIGH = 35.0

    def is_low(self) -> bool:
        return self.value is not None and self.value < self.LOW

    def is_high(self) -> bool:
        return self.value is not None and self.value > self.HIGH

    def assess(self) -> ItemAssessment:
        name = _get_item_name("k2o")
        if self.value is None:
            return ItemAssessment(
                name,
                None,
                "不明",
                "データがありません",
                "secondary",
                self.LOW,
                self.HIGH,
            )
        if self.is_low():
            return ItemAssessment(
                name,
                self.value,
                "低",
                "加里が不足しています",
                "warning",
                self.LOW,
                self.HIGH,
            )
        if self.is_high():
            return ItemAssessment(
                name,
                self.value,
                "過剰",
                "加里が過剰です",
                "danger",
                self.LOW,
                self.HIGH,
            )
        return ItemAssessment(
            name, self.value, "適正", "適正範囲内です", "success", self.LOW, self.HIGH
        )


@dataclass(frozen=True)
class PhosphorusAbsorptionVO:
    value: float | None

    def assess(self) -> ItemAssessment:
        name = _get_item_name("phosphorus_absorption")
        if self.value is None:
            return ItemAssessment(name, None, "不明", "データがありません", "secondary")

        recommendation = ""
        if self.value:
            low_p = self.value * 0.05
            high_p = self.value * 0.10
            recommendation = (
                f"適正なリン酸施用量は {low_p:.1f}〜{high_p:.1f} mg/100g です。"
            )

        return ItemAssessment(
            name,
            self.value,
            "参照",
            f"リン酸吸収係数に基づき、{recommendation}",
            "info",
        )


@dataclass(frozen=True)
class ReferenceVO:
    """判定基準がなく、参照値としてのみ扱う項目のためのVO"""

    value: float | None
    key: str

    def assess(self) -> ItemAssessment:
        name = _get_item_name(self.key)
        if self.value is None:
            return ItemAssessment(name, None, "不明", "データがありません", "secondary")
        return ItemAssessment(
            name,
            self.value,
            "参照",
            "判定基準が未設定のため、参照値として表示しています",
            "secondary",
        )
