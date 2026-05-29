from dataclasses import dataclass
from typing import Any

from . import chemical_thresholds as thresholds
from .report.fields import REPORT_FIELD_BY_KEY


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


@dataclass(frozen=True)
class ChemicalAssessmentVO:
    """
    化学分析値に基づく判定生成を行うValue Object

    Attributes:
        ph: pH(水素イオン濃度)
        ec: EC(電気伝導率)
        nh4n: NH4-N(アンモニア態窒素)
        no3n: NO3-N(硝酸態窒素)
        cec: CEC(保肥力)
        base_saturation: Base Saturation(塩基飽和度)
        p2o5: P2O5(可給態リン酸)
        humus: Humus(腐植)
    """

    ph: float | None = None
    ec: float | None = None
    nh4n: float | None = None
    no3n: float | None = None
    cec: float | None = None
    base_saturation: float | None = None
    p2o5: float | None = None
    humus: float | None = None

    @classmethod
    def from_measurements(cls, measurements: list[Any]) -> "ChemicalAssessmentVO":
        """
        複数の測定データから平均値を算出してVOを生成する。
        欠損値は集約時に除外する。
        """
        if not measurements:
            return cls()

        def avg(attr: str) -> float | None:
            values = [
                getattr(m, attr) for m in measurements if getattr(m, attr) is not None
            ]
            if not values:
                return None
            return sum(values) / len(values)

        return cls(
            ph=avg("ph"),
            ec=avg("ec"),
            nh4n=avg("nh4n"),
            no3n=avg("no3n"),
            cec=avg("cec"),
            base_saturation=avg("base_saturation"),
            p2o5=avg("p2o5"),
            humus=avg("humus"),
        )

    def assess_ph(self) -> ItemAssessment:
        return self._assess_range(
            self.ph,
            _get_item_name("ph"),
            thresholds.PH_LOW,
            thresholds.PH_HIGH,
            "酸性傾向です",
            "アルカリ性傾向です",
        )

    def assess_ec(self) -> ItemAssessment:
        return self._assess_range(
            self.ec,
            _get_item_name("ec"),
            thresholds.EC_LOW,
            thresholds.EC_HIGH,
            "肥切れの可能性があります",
            "肥料過多の可能性があります",
            label_high="過剰",
            level_high="danger",
        )

    def assess_nh4n(self) -> ItemAssessment:
        return self._assess_upper_limit(
            self.nh4n,
            _get_item_name("nh4n"),
            thresholds.NH4N_UPPER_LIMIT,
            "アンモニア態窒素が過剰です",
            label_high="過剰",
            level_high="danger",
        )

    def assess_no3n(self) -> ItemAssessment:
        return self._assess_upper_limit(
            self.no3n,
            _get_item_name("no3n"),
            thresholds.NO3N_UPPER_LIMIT,
            "硝酸態窒素が過剰です",
            label_high="過剰",
            level_high="danger",
        )

    def assess_cec(self) -> ItemAssessment:
        return self._assess_lower_limit(
            self.cec,
            _get_item_name("cec"),
            thresholds.CEC_LOW,
            "保肥力が低いです",
            "十分な保肥力があります",
        )

    def assess_base_saturation(self) -> ItemAssessment:
        name = _get_item_name("base_saturation")
        low = thresholds.BASE_SATURATION_LOWER_LIMIT
        high = thresholds.BASE_SATURATION_UPPER_LIMIT
        over = thresholds.BASE_SATURATION_OVER_LIMIT
        if self.base_saturation is None:
            return ItemAssessment(
                name, None, "不明", "データがありません", "secondary", low, high
            )
        if self.base_saturation > over:
            return ItemAssessment(
                name,
                self.base_saturation,
                "過剰",
                "塩基類が飽和状態を超えています",
                "danger",
                low,
                high,
            )
        if self.base_saturation < low:
            return ItemAssessment(
                name,
                self.base_saturation,
                "低",
                f"塩基類が不足しています（基準: {low}%以上）",
                "warning",
                low,
                high,
            )
        if self.base_saturation > high:
            return ItemAssessment(
                name,
                self.base_saturation,
                "過剰",
                f"塩基類が多めです（基準: {high}%以下）",
                "danger",
                low,
                high,
            )
        return ItemAssessment(
            name, self.base_saturation, "適正", "適正範囲内です", "success", low, high
        )

    def assess_p2o5(self) -> ItemAssessment:
        return self._assess_range(
            self.p2o5,
            _get_item_name("p2o5"),
            thresholds.P2O5_LOW,
            thresholds.P2O5_HIGH,
            "リン酸が不足しています",
            "リン酸が過剰です",
            label_high="過剰",
            level_high="danger",
        )

    def assess_humus(self) -> ItemAssessment:
        return self._assess_lower_limit(
            self.humus,
            _get_item_name("humus"),
            thresholds.HUMUS_LOW,
            "腐植が不足しています",
            level_low="danger",
        )

    def get_combination_comments(self) -> list[str]:
        comments = []
        if self.ph is not None and self.ec is not None:
            if self.ph > thresholds.PH_HIGH and self.ec < thresholds.EC_LOW:
                comments.append(
                    "高pHかつ低EC：石灰成分が過剰で、他の肥料成分が不足している可能性があります。"
                )
            elif self.ph > thresholds.PH_HIGH and self.ec > thresholds.EC_HIGH:
                comments.append(
                    "高pHかつ高EC：全体的に肥料成分が多すぎる（肥料過多）傾向にあります。"
                )
            elif self.ph < thresholds.PH_LOW and self.ec < thresholds.EC_LOW:
                comments.append(
                    "低pHかつ低EC：全体的に肥料成分が不足しています。石灰および肥料の投入を検討してください。"
                )
            elif self.ph < thresholds.PH_LOW and self.ec > thresholds.EC_HIGH:
                comments.append(
                    "低pHかつ高EC：窒素肥料が過剰で、土壌が酸性化している可能性があります。"
                )
        return comments

    def get_warnings(self) -> list[str]:
        warnings = []
        if (
            self.base_saturation is not None
            and self.base_saturation > thresholds.BASE_SATURATION_OVER_LIMIT
        ):
            name = _get_item_name("base_saturation")
            warnings.append(f"警告：{name}が{self.base_saturation:.1f}%と過剰です。")
        if self.humus is not None and self.humus < thresholds.HUMUS_LOW:
            name = _get_item_name("humus")
            warnings.append(
                f"警告：{name}が{self.humus:.1f}%と不足しています。堆肥の投入を推奨します。"
            )
        return warnings

    def get_summary(self) -> str:
        """総合サマリの生成"""
        if all(
            v is None
            for v in [
                self.ph,
                self.ec,
                self.nh4n,
                self.no3n,
                self.cec,
                self.base_saturation,
                self.p2o5,
                self.humus,
            ]
        ):
            return "判定に必要なデータが不足しています。"

        combos = self.get_combination_comments()
        if combos:
            return " ".join(combos)

        # 組み合わせがない場合は個別の状況から代表的なものを出す（簡易版）
        ph_res = self.assess_ph()
        ec_res = self.assess_ec()
        if ph_res.label == "適正" and ec_res.label == "適正":
            return "pH・ECともに適正範囲内です。良好な状態を維持してください。"

        return f"土壌診断の結果、{ph_res.label if ph_res.label != '適正' else ''}{'・' if ph_res.label != '適正' and ec_res.label != '適正' else ''}{ec_res.label if ec_res.label != '適正' else ''}な状態が見受けられます。詳細は各項目を確認してください。"

    @property
    def results(self) -> dict[str, ItemAssessment]:
        return {
            "ph": self.assess_ph(),
            "ec": self.assess_ec(),
            "nh4n": self.assess_nh4n(),
            "no3n": self.assess_no3n(),
            "cec": self.assess_cec(),
            "base_saturation": self.assess_base_saturation(),
            "p2o5": self.assess_p2o5(),
            "humus": self.assess_humus(),
        }

    @property
    def categorized_results(self) -> dict[str, list[ItemAssessment]]:
        """カテゴリーごとの判定結果を返す"""
        return {
            "窒素・EC関連": [
                self.assess_ec(),
                self.assess_nh4n(),
                self.assess_no3n(),
            ],
            "塩基類関連": [
                self.assess_ph(),
                self.assess_base_saturation(),
            ],
            "リン酸関連": [
                self.assess_p2o5(),
            ],
            "土壌ポテンシャル関連": [
                self.assess_cec(),
                self.assess_humus(),
            ],
        }

    @staticmethod
    def _assess_range(
        value: float | None,
        name: str,
        low: float,
        high: float,
        low_msg: str,
        high_msg: str,
        label_high: str = "高",
        level_high: str = "warning",
    ) -> ItemAssessment:
        if value is None:
            return ItemAssessment(
                name, None, "不明", "データがありません", "secondary", low, high
            )
        if value < low:
            return ItemAssessment(
                name,
                value,
                "低",
                f"{low_msg}（基準: {low}〜{high}）",
                "warning",
                low,
                high,
            )
        if value > high:
            return ItemAssessment(
                name,
                value,
                label_high,
                f"{high_msg}（基準: {low}〜{high}）",
                level_high,
                low,
                high,
            )
        return ItemAssessment(
            name, value, "適正", "適正範囲内です", "success", low, high
        )

    @staticmethod
    def _assess_upper_limit(
        value: float | None,
        name: str,
        limit: float,
        over_msg: str,
        label_high: str = "高",
        level_high: str = "warning",
    ) -> ItemAssessment:
        if value is None:
            return ItemAssessment(
                name, None, "不明", "データがありません", "secondary", None, limit
            )
        if value > limit:
            return ItemAssessment(
                name,
                value,
                label_high,
                f"{over_msg}（基準: {limit}以下）",
                level_high,
                None,
                limit,
            )
        return ItemAssessment(
            name, value, "適正", "適正範囲内です", "success", None, limit
        )

    @staticmethod
    def _assess_lower_limit(
        value: float | None,
        name: str,
        limit: float,
        under_msg: str,
        success_msg: str = "適正範囲内です",
        level_low: str = "warning",
    ) -> ItemAssessment:
        if value is None:
            return ItemAssessment(
                name, None, "不明", "データがありません", "secondary", limit, None
            )
        if value < limit:
            return ItemAssessment(
                name,
                value,
                "低",
                f"{under_msg}（基準: {limit}以上）",
                level_low,
                limit,
                None,
            )
        return ItemAssessment(name, value, "適正", success_msg, "success", limit, None)
