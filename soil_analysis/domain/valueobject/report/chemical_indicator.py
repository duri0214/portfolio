from dataclasses import dataclass

from .fields import REPORT_FIELDS, ReportField

REPORT_FIELD_BY_KEY: dict[str, ReportField] = {f.key: f for f in REPORT_FIELDS}


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
class BaseChemicalIndicatorVO:
    """
    化学指標のValue Objectの基底クラス

    Attributes:
        value: 測定値
        KEY: 項目キー (クラス定数)
        LOW: 下限閾値 (クラス定数)
        HIGH: 上限閾値 (クラス定数)
    """

    value: float | None

    # 各サブクラスで定義する定数 (クラス属性)
    KEY = ""
    LOW = None
    HIGH = None

    @staticmethod
    def _get_item_name(key: str) -> str:
        """項目キーから表示名 label(description) を取得する"""
        field = REPORT_FIELD_BY_KEY.get(key)
        if field:
            return f"{field.label}({field.description})"
        return key

    def is_low(self) -> bool:
        """下限値を下回っているか"""
        return self.value is not None and self.LOW is not None and self.value < self.LOW

    def is_high(self) -> bool:
        """上限値を上回っているか"""
        return (
            self.value is not None and self.HIGH is not None and self.value > self.HIGH
        )

    def assess(self) -> ItemAssessment:
        """項目の判定を行う"""
        name = self._get_item_name(self.KEY)
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
                getattr(self, "LOW_LABEL", "低"),
                getattr(self, "LOW_MESSAGE", "低めです"),
                getattr(self, "LOW_LEVEL", "danger"),
                self.LOW,
                self.HIGH,
            )
        if self.is_high():
            return ItemAssessment(
                name,
                self.value,
                getattr(self, "HIGH_LABEL", "高"),
                getattr(self, "HIGH_MESSAGE", "高めです"),
                getattr(self, "HIGH_LEVEL", "danger"),
                self.LOW,
                self.HIGH,
            )
        return ItemAssessment(
            name,
            self.value,
            "適正",
            getattr(self, "NORMAL_MESSAGE", "適正範囲内です"),
            "success",
            self.LOW,
            self.HIGH,
        )


@dataclass(frozen=True)
class PhVO(BaseChemicalIndicatorVO):
    """
    pH(水素イオン濃度)のValue Object

    Attributes:
        KEY: "ph"
        LOW: 6.0 (下限)
        HIGH: 7.0 (上限)
        LOW_MESSAGE: 酸性判定時のメッセージ
        HIGH_MESSAGE: アルカリ性判定時のメッセージ
    """

    KEY = "ph"
    LOW = 6.0
    HIGH = 7.0
    LOW_MESSAGE = "酸性傾向です"
    HIGH_MESSAGE = "アルカリ性傾向です"


@dataclass(frozen=True)
class EcVO(BaseChemicalIndicatorVO):
    """
    EC(電気伝導率)のValue Object

    Attributes:
        KEY: "ec"
        LOW: 0.1 (下限)
        HIGH: 0.5 (上限)
        HIGH_LABEL: "過剰"
        LOW_MESSAGE: 低判定時のメッセージ
        HIGH_MESSAGE: 高判定時のメッセージ
        HIGH_LEVEL: 高判定時の表示レベル
    """

    KEY = "ec"
    LOW = 0.1
    HIGH = 0.5
    HIGH_LABEL = "過剰"
    LOW_MESSAGE = "肥切れの可能性があります"
    HIGH_MESSAGE = "肥料過多の可能性があります"
    HIGH_LEVEL = "danger"


@dataclass(frozen=True)
class Nh4nVO(BaseChemicalIndicatorVO):
    """
    NH4-N(アンモニア態窒素)のValue Object

    閾値:
        HIGH: 5.0 (これを超えると過剰判定)
    """

    KEY = "nh4n"
    HIGH = 5.0
    HIGH_LABEL = "過剰"
    HIGH_MESSAGE = "アンモニア態窒素が過剰です"
    HIGH_LEVEL = "danger"


@dataclass(frozen=True)
class No3nVO(BaseChemicalIndicatorVO):
    """
    NO3-N(硝酸態窒素)のValue Object

    閾値:
        HIGH: 15.0 (これを超えると過剰判定)
    """

    KEY = "no3n"
    HIGH = 15.0
    HIGH_LABEL = "過剰"
    HIGH_MESSAGE = "硝酸態窒素が過剰です"
    HIGH_LEVEL = "danger"


@dataclass(frozen=True)
class CecVO(BaseChemicalIndicatorVO):
    """
    CEC(保肥力)のValue Object

    閾値:
        LOW: 12.0 (これ未満で低判定)
    """

    KEY = "cec"
    LOW = 12.0
    LOW_MESSAGE = "保肥力が低いです"
    NORMAL_MESSAGE = "十分な保肥力があります"


@dataclass(frozen=True)
class BaseSaturationVO(BaseChemicalIndicatorVO):
    """
    塩基飽和度(Base Saturation)のValue Object

    閾値 (CECに応じて動的に変化するが、基本値は以下の通り):
        LOW: 60.0 (下限)
        HIGH: 80.0 (上限)
        OVER: 100.0 (過剰)
    """

    KEY = "base_saturation"
    LOW = 60.0
    HIGH = 80.0
    OVER = 100.0

    def is_over(self) -> bool:
        return self.value is not None and self.value > self.OVER

    def assess(self, cec: float | None = None) -> ItemAssessment:
        name = self._get_item_name("base_saturation")

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
                "danger",
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
class P2o5VO(BaseChemicalIndicatorVO):
    """
    P2O5(可給態リン酸)のValue Object

    閾値:
        LOW: 50.0 (下限)
        HIGH: 100.0 (上限)
    """

    KEY = "p2o5"
    LOW = 50.0
    HIGH = 100.0
    HIGH_LABEL = "過剰"
    LOW_MESSAGE = "リン酸が不足しています。適正なリン酸施用が必要です。"
    HIGH_MESSAGE = "リン酸が過剰です。根瘤病のリスクを高める可能性があります。"
    HIGH_LEVEL = "danger"


@dataclass(frozen=True)
class HumusVO(BaseChemicalIndicatorVO):
    """
    Humus(腐植)のValue Object

    閾値:
        LOW: 3.0 (これ未満で低判定)
    """

    KEY = "humus"
    LOW = 3.0
    LOW_MESSAGE = "腐植が不足しています"
    LOW_LEVEL = "danger"


@dataclass(frozen=True)
class CaoVO(BaseChemicalIndicatorVO):
    """
    CaO(交換性石灰)のValue Object

    閾値:
        LOW: 300.0 (下限)
        HIGH: 450.0 (上限)
    """

    KEY = "cao"
    LOW = 300.0
    HIGH = 450.0
    HIGH_LABEL = "過剰"
    LOW_MESSAGE = "石灰が不足しています"
    HIGH_MESSAGE = (
        "石灰が過剰です。他の成分（苦土・加里等）の吸収阻害を招く恐れがあります。"
    )
    HIGH_LEVEL = "danger"


@dataclass(frozen=True)
class MgoVO(BaseChemicalIndicatorVO):
    """
    MgO(交換性苦土)のValue Object

    閾値:
        LOW: 30.0 (下限)
        HIGH: 50.0 (上限)
    """

    KEY = "mgo"
    LOW = 30.0
    HIGH = 50.0
    HIGH_LABEL = "過剰"
    LOW_MESSAGE = "苦土が不足しています"
    HIGH_MESSAGE = "苦土が過剰です"
    HIGH_LEVEL = "danger"


@dataclass(frozen=True)
class K2oVO(BaseChemicalIndicatorVO):
    """
    K2O(交換性加里)のValue Object

    閾値:
        LOW: 20.0 (下限)
        HIGH: 35.0 (上限)
    """

    KEY = "k2o"
    LOW = 20.0
    HIGH = 35.0
    HIGH_LABEL = "過剰"
    LOW_MESSAGE = "加里が不足しています"
    HIGH_MESSAGE = "加里が過剰です"
    HIGH_LEVEL = "danger"


@dataclass(frozen=True)
class PhosphorusAbsorptionVO(BaseChemicalIndicatorVO):
    """
    リン酸吸収係数のValue Object

    固有の判定閾値はないが、値に基づいた施肥設計の参考値を生成する。
    """

    def assess(self) -> ItemAssessment:
        name = self._get_item_name("phosphorus_absorption")
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
class ReferenceVO(BaseChemicalIndicatorVO):
    """判定基準がなく、参照値としてのみ扱う項目のためのVO"""

    key: str = ""

    def assess(self) -> ItemAssessment:
        name = self._get_item_name(self.key)
        if self.value is None:
            return ItemAssessment(name, None, "不明", "データがありません", "secondary")
        return ItemAssessment(
            name,
            self.value,
            "参照",
            "判定基準が未設定のため、参照値として表示しています",
            "info",
        )
