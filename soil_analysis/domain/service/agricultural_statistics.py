from dataclasses import dataclass
from datetime import date

from django.utils import timezone

from soil_analysis.domain.dataprovider.estat import EstatApiClient
from soil_analysis.domain.repository.agricultural_statistics import (
    AgriculturalStatisticsRepository,
)
from soil_analysis.domain.valueobject.estat import (
    AgriculturalRiskDashboard,
    AgriculturalRiskInput,
    AgriculturalRiskResult,
    EstatDatasetStatus,
    EstatValueRow,
    parse_estat_datetime,
)

ROKUNOHE_AREA_CODE = "02405"
RETIREMENT_TREND_COEFFICIENT = 0.35
ESTAT_DATA_VIEW_URL = "https://www.e-stat.go.jp/dbview"
CULTIVATED_AREA_DISTRIBUTION_KEY = "cultivated_area_distribution"
CULTIVATED_AREA_DISTRIBUTION_LABELS = {
    "1001": "計",
    "1002": "0.3ha未満",
    "1003": "0.3～0.5ha",
    "1004": "0.5～1.0ha",
    "1005": "1.0～1.5ha",
    "1006": "1.5～2.0ha",
    "1007": "2.0～3.0ha",
    "1008": "3.0～5.0ha",
    "1009": "5.0～10.0ha",
    "1010": "10.0～20.0ha",
    "1011": "20.0～30.0ha",
    "1012": "30.0～50.0ha",
    "1013": "50.0～100.0ha",
    "1014": "100.0～150.0ha",
    "1015": "150.0ha以上",
}

DEFAULT_ESTAT_DATASETS = [
    {
        "indicator_key": "total_cultivated_area",
        "display_name": "経営耕地面積",
        "stats_data_id": "0002068836",
        "filters": {
            "cdCat01": "1171",
            "cdCat02": "1001",
        },
        "unit": "ha",
        "category": "base",
    },
    {
        "indicator_key": CULTIVATED_AREA_DISTRIBUTION_KEY,
        "display_name": "経営耕地面積規模別面積",
        "stats_data_id": "0002068836",
        "filters": {
            "cdCat01": "1171",
        },
        "unit": "ha",
        "category": "base_distribution",
    },
    {
        "indicator_key": "age_70_plus_area",
        "display_name": "70歳以上の経営体が保有する面積",
        "stats_data_id": "TODO_AGE_70_PLUS_AREA",
        "filters": {},
        "unit": "ha",
        "category": "age",
    },
    {
        "indicator_key": "age_60s_area",
        "display_name": "60代の経営体が保有する面積",
        "stats_data_id": "TODO_AGE_60S_AREA",
        "filters": {},
        "unit": "ha",
        "category": "age",
    },
    {
        "indicator_key": "no_successor_ratio",
        "display_name": "後継者なし経営体割合",
        "stats_data_id": "TODO_NO_SUCCESSOR_RATIO",
        "filters": {},
        "unit": "%",
        "category": "succession",
    },
    {
        "indicator_key": "shrink_stop_intention_ratio",
        "display_name": "縮小・中止意向割合",
        "stats_data_id": "TODO_SHRINK_STOP_INTENTION",
        "filters": {},
        "unit": "%",
        "category": "intention",
    },
]


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


class AgriculturalRiskCalculator:
    """
    離農・管理不能農地リスクを説明可能な指標ベースで計算します。
    """

    @classmethod
    def calculate(cls, risk_input: AgriculturalRiskInput) -> AgriculturalRiskResult:
        """
        Issue 576 の仮説式に沿って離農リスクを算出します。

        Args:
            risk_input: 統計スナップショットから作成した入力値。

        Returns:
            AgriculturalRiskResult: 計算済みリスク指標。
        """
        total_area = risk_input.total_cultivated_area
        age_70_plus_area = risk_input.age_70_plus_area
        age_60s_area = risk_input.age_60s_area
        no_successor_ratio = risk_input.no_successor_ratio

        aging_risk = cls._ratio(age_70_plus_area, total_area)
        succession_risk = cls._to_percent(no_successor_ratio)
        intention_risk = cls._to_percent(risk_input.shrink_stop_intention_ratio)

        retirement_confirmed_area = cls._multiply(age_70_plus_area, no_successor_ratio)
        retirement_reserve_area = cls._multiply(
            age_60s_area,
            no_successor_ratio,
            RETIREMENT_TREND_COEFFICIENT,
        )
        unmanageable_candidate_area = cls._sum_optional(
            retirement_confirmed_area,
            retirement_reserve_area,
            risk_input.supplemental_unmanageable_area,
        )
        farmland_maintenance_rate = cls._maintenance_rate(
            total_area, unmanageable_candidate_area
        )
        return AgriculturalRiskResult(
            aging_risk=aging_risk,
            succession_risk=succession_risk,
            intention_risk=intention_risk,
            retirement_confirmed_area=retirement_confirmed_area,
            retirement_reserve_area=retirement_reserve_area,
            unmanageable_candidate_area=unmanageable_candidate_area,
            farmland_maintenance_rate=farmland_maintenance_rate,
        )

    @staticmethod
    def _multiply(*values: float | None) -> float | None:
        result = 1.0
        for value in values:
            if value is None:
                return None
            result *= value
        return round(result, 2)

    @staticmethod
    def _sum_optional(*values: float | None) -> float | None:
        if any(value is None for value in values):
            return None
        return round(sum(value for value in values if value is not None), 2)

    @staticmethod
    def _ratio(numerator: float | None, denominator: float | None) -> float | None:
        if numerator is None or not denominator:
            return None
        return round((numerator / denominator) * 100, 1)

    @staticmethod
    def _to_percent(value: float | None) -> float | None:
        if value is None:
            return None
        return round(value * 100, 1)

    @staticmethod
    def _maintenance_rate(
        total_area: float | None, unmanageable_candidate_area: float | None
    ) -> float | None:
        if not total_area or unmanageable_candidate_area is None:
            return None
        return round(((total_area - unmanageable_candidate_area) / total_area) * 100, 1)


class AgriculturalStatisticsService:
    """
    e-Stat 農業統計の取得、保存、離農リスク集計を扱うServiceです。
    """

    @classmethod
    def ensure_default_configuration(cls, area_code: str = ROKUNOHE_AREA_CODE):
        """
        六戸町と初期指標定義を作成します。

        Args:
            area_code: e-Stat 地域コード。
        """
        region = AgriculturalStatisticsRepository.get_or_create_default_region(
            area_code
        )
        for definition in DEFAULT_ESTAT_DATASETS:
            AgriculturalStatisticsRepository.ensure_dataset(definition)
        return region

    @classmethod
    def fetch_and_store(
        cls,
        *,
        client: EstatApiClient,
        area_code: str = ROKUNOHE_AREA_CODE,
        target_date: date | None = None,
        force: bool = False,
        dry_run: bool = False,
    ) -> EstatFetchResult:
        """
        対象地域のe-Stat統計を取得し、変更がある値だけ保存します。

        Args:
            client: e-Stat API クライアント。
            area_code: e-Stat 地域コード。
            target_date: 取得日の代替値。
            force: True の場合は同一値でも履歴として保存する。
            dry_run: True の場合はDBへ保存しない。

        Returns:
            EstatFetchResult: バッチ実行結果。
        """
        region = cls.ensure_default_configuration(area_code)
        datasets = AgriculturalStatisticsRepository.get_datasets()
        fetched_at = timezone.now()
        default_period_label = str(target_date or fetched_at.date())
        created_count = 0
        skipped_count = 0
        dry_run_count = 0
        skipped_dataset_keys = []

        for dataset in datasets:
            if dataset.stats_data_id.startswith("TODO_"):
                skipped_dataset_keys.append(dataset.indicator_key)
                continue

            response = client.get_stats_data(
                dataset.stats_data_id, region.area_code, dataset.filters
            )
            rows = cls._extract_value_rows(response, default_period_label)
            estat_updated_at = cls._extract_estat_updated_at(response)

            for row in rows:
                if dry_run:
                    dry_run_count += 1
                    continue
                _, created = AgriculturalStatisticsRepository.save_snapshot(
                    region=region,
                    dataset=dataset,
                    period_label=row.period_label,
                    value=row.value,
                    fetched_at=fetched_at,
                    estat_updated_at=estat_updated_at,
                    raw_data=row.raw_data,
                    source_hash=row.source_hash,
                    force=force,
                )
                if created:
                    created_count += 1
                else:
                    skipped_count += 1

        if not dry_run and AgriculturalStatisticsRepository.get_snapshots(region):
            cls.calculate_and_save_report(region=region, report_date=fetched_at.date())

        return EstatFetchResult(
            created_count=created_count,
            skipped_count=skipped_count,
            dry_run_count=dry_run_count,
            skipped_dataset_keys=skipped_dataset_keys,
        )

    @classmethod
    def calculate_and_save_report(cls, *, region, report_date: date):
        """
        最新スナップショットから離農リスクレポートを保存します。

        Args:
            region: 対象地域。
            report_date: 集計日。
        """
        latest = AgriculturalStatisticsRepository.get_latest_snapshot_values(region)
        risk_input = cls._build_risk_input(latest)
        result = AgriculturalRiskCalculator.calculate(risk_input)
        return AgriculturalStatisticsRepository.save_risk_report(
            region=region,
            report_date=report_date,
            values={
                "total_cultivated_area": risk_input.total_cultivated_area,
                "age_70_plus_area": risk_input.age_70_plus_area,
                "age_60s_area": risk_input.age_60s_area,
                "no_successor_ratio": risk_input.no_successor_ratio,
                "shrink_stop_intention_ratio": (risk_input.shrink_stop_intention_ratio),
                "supplemental_unmanageable_area": (
                    risk_input.supplemental_unmanageable_area
                ),
                "aging_risk": result.aging_risk,
                "succession_risk": result.succession_risk,
                "intention_risk": result.intention_risk,
                "retirement_confirmed_area": result.retirement_confirmed_area,
                "retirement_reserve_area": result.retirement_reserve_area,
                "unmanageable_candidate_area": (result.unmanageable_candidate_area),
                "farmland_maintenance_rate": result.farmland_maintenance_rate,
            },
        )

    @classmethod
    def build_dashboard(
        cls, area_code: str = ROKUNOHE_AREA_CODE
    ) -> AgriculturalRiskDashboard:
        """
        離農・管理不能農地リスク画面の表示モデルを作成します。

        Args:
            area_code: e-Stat 地域コード。

        Returns:
            AgriculturalRiskDashboard: 画面表示用データ。
        """
        region = cls.ensure_default_configuration(area_code)
        latest_report = AgriculturalStatisticsRepository.get_latest_risk_report(region)
        snapshots = AgriculturalStatisticsRepository.get_snapshots(region)
        report_trend = AgriculturalStatisticsRepository.get_risk_report_trend(region)
        age_area_rows = cls._build_age_area_rows(latest_report)
        distribution_snapshots = (
            AgriculturalStatisticsRepository.get_latest_snapshots_by_period(
                region, CULTIVATED_AREA_DISTRIBUTION_KEY
            )
        )
        cultivated_area_distribution_rows = (
            cls._build_cultivated_area_distribution_rows(distribution_snapshots)
        )
        datasets = AgriculturalStatisticsRepository.get_datasets()
        latest_snapshot_values = (
            AgriculturalStatisticsRepository.get_latest_snapshot_values(region)
        )
        dataset_status_rows = cls._build_dataset_status_rows(
            datasets, latest_snapshot_values
        )
        return AgriculturalRiskDashboard(
            region_name=region.name,
            prefecture_name=region.prefecture_name,
            area_code=region.area_code,
            latest_report=latest_report,
            snapshots=snapshots,
            report_trend=report_trend,
            age_area_rows=age_area_rows,
            cultivated_area_distribution_rows=cultivated_area_distribution_rows,
            dataset_status_rows=dataset_status_rows,
            latest_fetched_at=cls._latest_fetched_at(dataset_status_rows),
            latest_estat_updated_at=cls._latest_estat_updated_at(dataset_status_rows),
            has_data=latest_report is not None or bool(snapshots),
        )

    @classmethod
    def _extract_value_rows(
        cls, response: dict, default_period_label: str
    ) -> list[EstatValueRow]:
        statistical_data = response.get("GET_STATS_DATA", {}).get(
            "STATISTICAL_DATA", {}
        )
        value_data = statistical_data.get("DATA_INF", {}).get("VALUE", [])
        if isinstance(value_data, dict):
            value_data = [value_data]
        return [
            EstatValueRow.from_raw(raw_data, default_period_label)
            for raw_data in value_data
            if isinstance(raw_data, dict)
        ]

    @classmethod
    def _build_cultivated_area_distribution_rows(
        cls, snapshots_by_period: dict
    ) -> list[dict[str, float | str | None]]:
        total_snapshot = snapshots_by_period.get("1001")
        total_value = total_snapshot.value if total_snapshot is not None else None
        rows = []
        for period_label, label in CULTIVATED_AREA_DISTRIBUTION_LABELS.items():
            if period_label == "1001":
                continue
            snapshot = snapshots_by_period.get(period_label)
            value = snapshot.value if snapshot is not None else None
            rows.append(
                {
                    "label": label,
                    "period_label": period_label,
                    "value": value,
                    "unit": "ha",
                    "share": AgriculturalRiskCalculator._ratio(value, total_value),
                }
            )
        return rows

    @staticmethod
    def _extract_estat_updated_at(response: dict):
        stats_data = response.get("GET_STATS_DATA", {})
        result_inf = stats_data.get("RESULT_INF", {})
        table_inf = stats_data.get("STATISTICAL_DATA", {}).get("TABLE_INF", {})
        return parse_estat_datetime(
            result_inf.get("DATE")
            or table_inf.get("@updatedDate")
            or table_inf.get("UPDATED_DATE")
        )

    @classmethod
    def _build_risk_input(cls, latest: dict) -> AgriculturalRiskInput:
        return AgriculturalRiskInput(
            total_cultivated_area=cls._value(latest, "total_cultivated_area"),
            age_70_plus_area=cls._value(latest, "age_70_plus_area"),
            age_60s_area=cls._value(latest, "age_60s_area"),
            no_successor_ratio=cls._ratio_value(latest, "no_successor_ratio"),
            shrink_stop_intention_ratio=cls._ratio_value(
                latest, "shrink_stop_intention_ratio"
            ),
            supplemental_unmanageable_area=0.0,
        )

    @staticmethod
    def _value(latest: dict, indicator_key: str) -> float | None:
        snapshot = latest.get(indicator_key)
        if snapshot is None:
            return None
        return snapshot.value

    @classmethod
    def _ratio_value(cls, latest: dict, indicator_key: str) -> float | None:
        value = cls._value(latest, indicator_key)
        if value is None:
            return None
        if value > 1:
            return value / 100
        return value

    @staticmethod
    def _build_age_area_rows(latest_report) -> list[dict[str, float | str | None]]:
        if latest_report is None:
            return []
        return [
            {
                "label": "60代",
                "value": latest_report.age_60s_area,
                "unit": "ha",
            },
            {
                "label": "70歳以上",
                "value": latest_report.age_70_plus_area,
                "unit": "ha",
            },
        ]

    @classmethod
    def _build_dataset_status_rows(
        cls, datasets: list, latest_snapshot_values: dict
    ) -> list[EstatDatasetStatus]:
        return [
            cls._build_dataset_status_row(dataset, latest_snapshot_values)
            for dataset in datasets
        ]

    @classmethod
    def _build_dataset_status_row(
        cls, dataset, latest_snapshot_values: dict
    ) -> EstatDatasetStatus:
        snapshot = latest_snapshot_values.get(dataset.indicator_key)
        is_configured = not dataset.stats_data_id.startswith("TODO_")
        if snapshot is not None:
            status_label = "取得済み"
        elif is_configured:
            status_label = "未取得"
        else:
            status_label = "未実装（TODO）"
        return EstatDatasetStatus(
            indicator_key=dataset.indicator_key,
            display_name=dataset.display_name,
            stats_data_id=dataset.stats_data_id if is_configured else "未設定",
            source_page_url=(
                cls._source_page_url(dataset.stats_data_id) if is_configured else ""
            ),
            filters_label=cls._filters_label(dataset.filters),
            unit=dataset.unit,
            status_label=status_label,
            latest_value=snapshot.value if snapshot is not None else None,
            period_label=snapshot.period_label if snapshot is not None else None,
            fetched_at=snapshot.fetched_at if snapshot is not None else None,
            estat_updated_at=(
                snapshot.estat_updated_at if snapshot is not None else None
            ),
        )

    @staticmethod
    def _source_page_url(stats_data_id: str) -> str:
        return f"{ESTAT_DATA_VIEW_URL}?sid={stats_data_id}"

    @staticmethod
    def _filters_label(filters: dict) -> str:
        if not filters:
            return "なし"
        return ", ".join(f"{key}={value}" for key, value in sorted(filters.items()))

    @staticmethod
    def _latest_fetched_at(rows: list[EstatDatasetStatus]):
        fetched_values = [row.fetched_at for row in rows if row.fetched_at is not None]
        if not fetched_values:
            return None
        return max(fetched_values)

    @staticmethod
    def _latest_estat_updated_at(rows: list[EstatDatasetStatus]):
        updated_values = [
            row.estat_updated_at for row in rows if row.estat_updated_at is not None
        ]
        if not updated_values:
            return None
        return max(updated_values)
