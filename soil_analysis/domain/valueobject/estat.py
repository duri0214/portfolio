import hashlib
import json
from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone


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
    def from_raw(
        cls,
        raw_data: dict,
        default_period_label: str,
        table_metadata: dict | None = None,
        class_metadata: dict | None = None,
    ) -> "EstatValueRow":
        """
        e-Stat の VALUE レコードから保存用VOを作成します。

        Args:
            raw_data: e-Stat API の VALUE レコード。
            default_period_label: VALUE に時間軸がない場合の代替期間。
            table_metadata: e-Stat TABLE_INF から画面表示に必要な情報だけ抜粋した値。
            class_metadata: e-Stat CLASS_INF から分類コードの表示名を抜粋した値。

        Returns:
            EstatValueRow: 保存用に正規化した統計値。
        """
        period_label = str(
            raw_data.get("@time")
            or raw_data.get("@cat02")
            or raw_data.get("@cat01")
            or raw_data.get("@area")
            or default_period_label
        )
        value_text = raw_data.get("$") or raw_data.get("#text")
        value = cls._to_float(value_text)
        unit = str(raw_data.get("@unit", ""))
        enriched_raw_data = dict(raw_data)
        if table_metadata:
            enriched_raw_data["_table_metadata"] = table_metadata
        if class_metadata:
            enriched_raw_data["_class_metadata"] = class_metadata
        return cls(
            period_label=period_label,
            value=value,
            unit=unit,
            raw_data=enriched_raw_data,
            source_hash=cls._build_hash(enriched_raw_data),
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
class EstatDatasetStatus:
    """
    e-Stat 指標ごとの取得状況を画面に表示するための値です。

    Attributes:
        indicator_key: レポート計算で使う指標キー。
        display_name: 画面に表示する指標名。
        stats_data_id: e-Stat 統計表表示 ID。
        source_page_url: e-Stat の目検用統計表ページ URL。
        filters_label: e-Stat API に渡す絞り込み条件の表示文字列。
        unit: 値の単位。
        status_label: 取得済み、未設定などの状態。
        data_period_label: 統計値のデータ時点。
        fetched_at: このアプリが取得した日時。
        estat_updated_at: e-Stat 側の公開・更新日時。
    """

    indicator_key: str
    display_name: str
    stats_data_id: str
    source_page_url: str
    filters_label: str
    unit: str
    status_label: str
    data_period_label: str | None
    fetched_at: datetime | None
    estat_updated_at: datetime | None


@dataclass(frozen=True)
class SupplementalRiskIndicatorStatus:
    """
    e-Stat 以外の補助指標を画面に表示するための値です。

    Attributes:
        indicator_key: 指標キー。
        display_name: 画面に表示する指標名。
        source_name: 取得元名。
        source_url: 取得元URL。
        region_label: 全国、青森県などの地域粒度。
        period_label: 統計値の時点。
        value: 統計値。
        unit: 単位。
        category: 指標カテゴリ。
        note: 指標の読み方や注意点。
    """

    indicator_key: str
    display_name: str
    source_name: str
    source_url: str
    region_label: str
    period_label: str
    value: float | None
    unit: str
    category: str
    note: str


@dataclass(frozen=True)
class EstatFetchResult:
    """
    e-Stat 取得バッチの結果です。

    Attributes:
        created_count: 新規保存したスナップショット数。
        skipped_count: 既存と同一で保存しなかったスナップショット数。
        dry_run_count: dry-run で保存対象だったスナップショット数。
        skipped_dataset_keys: 統計表ID未設定のため取得をスキップした指標キー。
    """

    created_count: int
    skipped_count: int
    dry_run_count: int
    skipped_dataset_keys: list[str]


@dataclass(frozen=True)
class AgriculturalRiskDashboard:
    """
    離農・管理不能農地リスク画面に渡す表示用データです。

    Attributes:
        region_name: 対象地域名。
        prefecture_name: 都道府県名。
        area_code: e-Stat 地域コード。
        latest_report: 最新リスクレポート。
        age_area_rows: 年代別に集計した経営体数行。
        cultivated_area_distribution_rows: 経営耕地面積規模別面積の分布行。
        successor_status_rows: 後継者確保状況別の経営体数行。
        cultivated_area_distribution_sources: 分布表示に使った統計指標。
        supplemental_indicator_rows: e-Stat 以外の補助指標行。
        inheritance_land_reversion_summary: 相続土地国庫帰属制度の全国統計表示データ。
        kpi_basis: KPIごとの地域粒度・データ時点・根拠。
        dataset_status_rows: 指標ごとの取得状況。
        has_data: 表示可能な統計データがあるかどうか。
    """

    region_name: str
    prefecture_name: str
    area_code: str
    latest_report: object | None
    age_area_rows: list[dict[str, float | str | None]]
    cultivated_area_distribution_rows: list[dict[str, float | str | None]]
    successor_status_rows: list[dict[str, float | str | None]]
    cultivated_area_distribution_sources: list[EstatDatasetStatus]
    supplemental_indicator_rows: list[SupplementalRiskIndicatorStatus]
    inheritance_land_reversion_summary: dict
    kpi_basis: dict
    dataset_status_rows: list[EstatDatasetStatus]
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
        parsed = datetime.fromisoformat(value_text)
    except ValueError:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed
