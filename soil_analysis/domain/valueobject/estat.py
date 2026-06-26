import hashlib
import json
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class EstatValueRow:
    """
    e-Stat の VALUE レコードを保存しやすい形へ正規化した値です。

    Attributes:
        period_label: 統計値の対象期間。
        value: 統計値。数値化できない場合は None。
        unit: 単位。
        raw_data: e-Stat の VALUE レコード。
        source_hash: 重複保存判定に使うハッシュ。
    """

    period_label: str
    value: float | None
    unit: str
    raw_data: dict
    source_hash: str

    @classmethod
    def from_raw(cls, raw_data: dict, default_period_label: str) -> "EstatValueRow":
        """
        e-Stat の VALUE レコードから保存用VOを作成します。

        Args:
            raw_data: e-Stat API の VALUE レコード。
            default_period_label: VALUE に時間軸がない場合の代替期間。

        Returns:
            EstatValueRow: 保存用に正規化した統計値。
        """
        period_label = str(
            raw_data.get("@time")
            or raw_data.get("@cat01")
            or raw_data.get("@area")
            or default_period_label
        )
        value_text = raw_data.get("$") or raw_data.get("#text")
        value = cls._to_float(value_text)
        unit = str(raw_data.get("@unit", ""))
        return cls(
            period_label=period_label,
            value=value,
            unit=unit,
            raw_data=raw_data,
            source_hash=cls._build_hash(raw_data),
        )

    @staticmethod
    def _to_float(value_text: object) -> float | None:
        if value_text in (None, "", "-"):
            return None
        try:
            return float(str(value_text).replace(",", ""))
        except ValueError:
            return None

    @staticmethod
    def _build_hash(raw_data: dict) -> str:
        serialized = json.dumps(raw_data, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AgriculturalRiskInput:
    """
    離農・管理不能農地リスク計算に使う入力値です。

    Attributes:
        total_cultivated_area: 現在の経営耕地面積。
        age_70_plus_area: 70歳以上の経営体が保有する面積。
        age_60s_area: 60代の経営体が保有する面積。
        no_successor_ratio: 後継者なし割合。0.0から1.0の比率。
        shrink_stop_intention_ratio: 縮小・中止意向の割合。0.0から1.0の比率。
        supplemental_unmanageable_area: 補助指標による管理不能化候補面積。
    """

    total_cultivated_area: float | None
    age_70_plus_area: float | None
    age_60s_area: float | None
    no_successor_ratio: float | None
    shrink_stop_intention_ratio: float | None
    supplemental_unmanageable_area: float = 0.0


@dataclass(frozen=True)
class AgriculturalRiskResult:
    """
    離農・管理不能農地リスク計算の結果です。

    Attributes:
        aging_risk: 高齢化リスク。
        succession_risk: 継承リスク。
        intention_risk: 意向リスク。
        retirement_confirmed_area: 離農確定候補面積。
        retirement_reserve_area: 離農予備軍面積。
        unmanageable_candidate_area: 管理不能化候補面積。
        farmland_maintenance_rate: 10年後の農地維持率。
    """

    aging_risk: float | None
    succession_risk: float | None
    intention_risk: float | None
    retirement_confirmed_area: float | None
    retirement_reserve_area: float | None
    unmanageable_candidate_area: float | None
    farmland_maintenance_rate: float | None


@dataclass(frozen=True)
class AgriculturalRiskDashboard:
    """
    離農・管理不能農地リスク画面に渡す表示用データです。

    Attributes:
        region_name: 対象地域名。
        prefecture_name: 都道府県名。
        area_code: e-Stat 地域コード。
        latest_report: 最新リスクレポート。
        snapshots: 取得済み統計スナップショット。
        report_trend: リスクレポートの時系列。
        age_area_rows: 年齢階層別面積として表示する行。
        has_data: 表示可能な統計データがあるかどうか。
    """

    region_name: str
    prefecture_name: str
    area_code: str
    latest_report: object | None
    snapshots: list
    report_trend: list
    age_area_rows: list[dict[str, float | str | None]]
    has_data: bool


def parse_estat_datetime(value: object) -> datetime | None:
    """
    e-Stat の日時文字列を datetime に変換します。

    Args:
        value: e-Stat レスポンス内の更新日時らしき値。

    Returns:
        datetime | None: 変換できた日時。変換できない場合は None。
    """
    if not value:
        return None
    value_text = str(value).replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(value_text)
    except ValueError:
        return None
