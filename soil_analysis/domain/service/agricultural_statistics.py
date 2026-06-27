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
    EstatFetchResult,
    EstatValueRow,
    SupplementalRiskIndicatorStatus,
    parse_estat_datetime,
)

DEFAULT_AREA_CODE = "02405"
RETIREMENT_TREND_COEFFICIENT = 0.35
ESTAT_DATA_VIEW_URL = "https://www.e-stat.go.jp/dbview"
DERIVED_INDICATOR_KEYS = {"total_cultivated_area"}
CALCULATION_ONLY_INDICATOR_KEYS = {
    "age_60s_area",
    "age_70_plus_area",
    "no_successor_ratio",
    "shrink_stop_intention_ratio",
}
CULTIVATED_AREA_DISTRIBUTION_KEY = "cultivated_area_distribution"
CULTIVATED_AREA_DISTRIBUTION_COUNT_KEY = "cultivated_area_distribution_count"
OPERATOR_AGE_DISTRIBUTION_KEY = "operator_age_distribution_count"
SUCCESSOR_STATUS_DISTRIBUTION_KEY = "successor_status_count"
ABANDONED_FARMLAND_AREA_KEY = "abandoned_farmland_area_2015"
MOJ_INHERITANCE_SOURCE_URL = "https://www.moj.go.jp/MINJI/minji05_00579.html"
CULTIVATED_AREA_DISTRIBUTION_FALLBACK_LABELS = {
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
OPERATOR_AGE_GROUP_CODES = {
    "30歳未満": {"1002", "1003", "1004"},
    "30代": {"1005", "1006"},
    "40代": {"1007", "1008"},
    "50代": {"1009", "1010"},
    "60代": {"1011", "1012"},
    "70歳以上": {"1013", "1014", "1015", "1016"},
}
INHERITANCE_LAND_REVERSION_TOTAL_KEY = "inheritance_land_reversion_applications_total"
INHERITANCE_LAND_REVERSION_APPLICATION_KEYS = [
    "inheritance_land_reversion_applications_farmland",
    "inheritance_land_reversion_applications_residential",
    "inheritance_land_reversion_applications_forest",
    "inheritance_land_reversion_applications_other",
]

DEFAULT_ESTAT_DATASETS = [
    {
        "indicator_key": CULTIVATED_AREA_DISTRIBUTION_KEY,
        "display_name": "経営耕地面積規模別面積",
        "stats_data_id": "0002068836",
        "filters": {
            "cdCat01": "1171",
        },
        "unit": "ha",
        "category": "base_distribution",
        "fallback_data_period_label": "2020年農林業センサス（2020年1月〜2020年12月）",
    },
    {
        "indicator_key": CULTIVATED_AREA_DISTRIBUTION_COUNT_KEY,
        "display_name": "経営耕地面積規模別経営体数",
        "stats_data_id": "0002068830",
        "filters": {
            "cdCat01": "1171",
        },
        "unit": "経営体",
        "category": "base_distribution",
        "fallback_data_period_label": "2020年農林業センサス（2020年1月〜2020年12月）",
    },
    {
        "indicator_key": OPERATOR_AGE_DISTRIBUTION_KEY,
        "display_name": "経営主年齢階層別経営体数",
        "stats_data_id": "0002068866",
        "filters": {
            "cdCat01": "1171",
        },
        "unit": "経営体",
        "category": "age",
        "fallback_data_period_label": "2020年農林業センサス（2020年1月〜2020年12月）",
    },
    {
        "indicator_key": SUCCESSOR_STATUS_DISTRIBUTION_KEY,
        "display_name": "5年以内の後継者確保状況別経営体数",
        "stats_data_id": "0002068879",
        "filters": {
            "cdCat01": "1171",
        },
        "unit": "経営体",
        "category": "succession",
        "fallback_data_period_label": "2020年農林業センサス（2020年1月〜2020年12月）",
    },
    {
        "indicator_key": ABANDONED_FARMLAND_AREA_KEY,
        "display_name": "耕作放棄地面積（2015年）",
        "stats_data_id": "0003205603",
        "filters": {
            "cdTab": "0050",
            "cdCat01": "100",
        },
        "unit": "ha",
        "category": "abandoned_farmland",
        "fallback_data_period_label": "2015年農林業センサス（2015年1月〜2015年12月）",
    },
]

DEFAULT_SUPPLEMENTAL_INDICATORS = [
    {
        "indicator_key": "inheritance_land_reversion_applications_total",
        "display_name": "相続土地国庫帰属制度 申請件数",
        "source_name": "法務省 相続土地国庫帰属制度の統計",
        "source_url": MOJ_INHERITANCE_SOURCE_URL,
        "region_label": "全国",
        "period_label": "令和8年5月31日現在",
        "value": 5545,
        "unit": "件",
        "category": "inheritance_land_reversion",
        "note": "速報値。現時点では単月更新ページの累計値として扱い、時系列化は今後の取得拡張で対応する。",
    },
    {
        "indicator_key": "inheritance_land_reversion_applications_farmland",
        "display_name": "相続土地国庫帰属制度 申請件数（田・畑）",
        "source_name": "法務省 相続土地国庫帰属制度の統計",
        "source_url": MOJ_INHERITANCE_SOURCE_URL,
        "region_label": "全国",
        "period_label": "令和8年5月31日現在",
        "value": 2169,
        "unit": "件",
        "category": "inheritance_land_reversion",
        "note": "申請件数の地目別内訳。合計値の一部であり、独立した別指標ではない。",
    },
    {
        "indicator_key": "inheritance_land_reversion_applications_residential",
        "display_name": "相続土地国庫帰属制度 申請件数（宅地）",
        "source_name": "法務省 相続土地国庫帰属制度の統計",
        "source_url": MOJ_INHERITANCE_SOURCE_URL,
        "region_label": "全国",
        "period_label": "令和8年5月31日現在",
        "value": 1916,
        "unit": "件",
        "category": "inheritance_land_reversion",
        "note": "申請件数の地目別内訳。合計値の一部であり、独立した別指標ではない。",
    },
    {
        "indicator_key": "inheritance_land_reversion_applications_forest",
        "display_name": "相続土地国庫帰属制度 申請件数（山林）",
        "source_name": "法務省 相続土地国庫帰属制度の統計",
        "source_url": MOJ_INHERITANCE_SOURCE_URL,
        "region_label": "全国",
        "period_label": "令和8年5月31日現在",
        "value": 850,
        "unit": "件",
        "category": "inheritance_land_reversion",
        "note": "申請件数の地目別内訳。合計値の一部であり、独立した別指標ではない。",
    },
    {
        "indicator_key": "inheritance_land_reversion_applications_other",
        "display_name": "相続土地国庫帰属制度 申請件数（その他）",
        "source_name": "法務省 相続土地国庫帰属制度の統計",
        "source_url": MOJ_INHERITANCE_SOURCE_URL,
        "region_label": "全国",
        "period_label": "令和8年5月31日現在",
        "value": 610,
        "unit": "件",
        "category": "inheritance_land_reversion",
        "note": "申請件数の地目別内訳。合計値の一部であり、独立した別指標ではない。",
    },
    {
        "indicator_key": "inheritance_land_reversion_approved_farmland",
        "display_name": "相続土地国庫帰属制度 帰属件数（農用地）",
        "source_name": "法務省 相続土地国庫帰属制度の統計",
        "source_url": MOJ_INHERITANCE_SOURCE_URL,
        "region_label": "全国",
        "period_label": "令和8年5月31日現在",
        "value": 879,
        "unit": "件",
        "category": "inheritance_land_reversion",
        "note": "帰属件数の種目別内訳。合計申請とは母数が異なるため、補足値として扱う。",
    },
]


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
        )
        if unmanageable_candidate_area is not None:
            unmanageable_candidate_area = cls._sum_optional(
                unmanageable_candidate_area,
                risk_input.supplemental_unmanageable_area,
            )
        elif risk_input.supplemental_unmanageable_area:
            unmanageable_candidate_area = risk_input.supplemental_unmanageable_area
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
    def ensure_default_configuration(cls, area_code: str = DEFAULT_AREA_CODE):
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
        for definition in DEFAULT_SUPPLEMENTAL_INDICATORS:
            AgriculturalStatisticsRepository.upsert_supplemental_indicator(definition)
        return region

    @classmethod
    def fetch_and_store(
        cls,
        *,
        client: EstatApiClient,
        area_code: str = DEFAULT_AREA_CODE,
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
        datasets = cls._fetch_target_datasets(
            AgriculturalStatisticsRepository.get_datasets()
        )
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
        distribution_snapshots = (
            AgriculturalStatisticsRepository.get_latest_snapshots_by_period(
                region, CULTIVATED_AREA_DISTRIBUTION_KEY
            )
        )
        successor_snapshots = (
            AgriculturalStatisticsRepository.get_latest_snapshots_by_period(
                region, SUCCESSOR_STATUS_DISTRIBUTION_KEY
            )
        )
        risk_input = cls._build_risk_input(
            latest, distribution_snapshots, successor_snapshots
        )
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
        cls, area_code: str = DEFAULT_AREA_CODE
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
        latest_snapshot_values = (
            AgriculturalStatisticsRepository.get_latest_snapshot_values(region)
        )
        age_distribution_snapshots = (
            AgriculturalStatisticsRepository.get_latest_snapshots_by_period(
                region, OPERATOR_AGE_DISTRIBUTION_KEY
            )
        )
        age_area_rows = cls._build_age_group_rows(age_distribution_snapshots)
        distribution_snapshots = (
            AgriculturalStatisticsRepository.get_latest_snapshots_by_period(
                region, CULTIVATED_AREA_DISTRIBUTION_KEY
            )
        )
        distribution_count_snapshots = (
            AgriculturalStatisticsRepository.get_latest_snapshots_by_period(
                region, CULTIVATED_AREA_DISTRIBUTION_COUNT_KEY
            )
        )
        cultivated_area_distribution_rows = (
            cls._build_cultivated_area_distribution_rows(
                distribution_snapshots, distribution_count_snapshots
            )
        )
        cultivated_area_distribution_summary = (
            cls._build_cultivated_area_distribution_summary(
                cultivated_area_distribution_rows
            )
        )
        successor_snapshots = (
            AgriculturalStatisticsRepository.get_latest_snapshots_by_period(
                region, SUCCESSOR_STATUS_DISTRIBUTION_KEY
            )
        )
        successor_status_rows = cls._build_classification_rows(
            successor_snapshots,
            skip_subtotal=True,
        )
        datasets = cls._display_datasets(
            AgriculturalStatisticsRepository.get_datasets()
        )
        dataset_status_rows = cls._build_dataset_status_rows(
            datasets,
            latest_snapshot_values,
            distribution_snapshots,
        )
        distribution_sources = cls._distribution_source_rows(dataset_status_rows)
        supplemental_indicator_rows = cls._build_supplemental_indicator_rows(
            AgriculturalStatisticsRepository.get_supplemental_indicators()
        )
        inheritance_land_reversion_summary = (
            cls._build_inheritance_land_reversion_summary(supplemental_indicator_rows)
        )
        kpi_basis = cls._build_kpi_basis(dataset_status_rows)
        return AgriculturalRiskDashboard(
            region_name=region.name,
            prefecture_name=region.prefecture_name,
            area_code=region.area_code,
            latest_report=latest_report,
            age_area_rows=age_area_rows,
            cultivated_area_distribution_summary=cultivated_area_distribution_summary,
            cultivated_area_distribution_rows=cultivated_area_distribution_rows,
            successor_status_rows=successor_status_rows,
            cultivated_area_distribution_sources=distribution_sources,
            supplemental_indicator_rows=supplemental_indicator_rows,
            inheritance_land_reversion_summary=inheritance_land_reversion_summary,
            kpi_basis=kpi_basis,
            dataset_status_rows=dataset_status_rows,
            has_data=(
                latest_report is not None
                or bool(snapshots)
                or bool(supplemental_indicator_rows)
            ),
        )

    @classmethod
    def _extract_value_rows(
        cls, response: dict, default_period_label: str
    ) -> list[EstatValueRow]:
        statistical_data = response.get("GET_STATS_DATA", {}).get(
            "STATISTICAL_DATA", {}
        )
        table_metadata = cls._extract_table_metadata(response)
        class_metadata = cls._extract_class_metadata(response)
        value_data = statistical_data.get("DATA_INF", {}).get("VALUE", [])
        if isinstance(value_data, dict):
            value_data = [value_data]
        return [
            EstatValueRow.from_raw(
                raw_data,
                default_period_label,
                table_metadata=table_metadata,
                class_metadata=class_metadata,
            )
            for raw_data in value_data
            if isinstance(raw_data, dict)
        ]

    @staticmethod
    def _extract_table_metadata(response: dict) -> dict:
        table_inf = (
            response.get("GET_STATS_DATA", {})
            .get("STATISTICAL_DATA", {})
            .get("TABLE_INF", {})
        )
        if not isinstance(table_inf, dict):
            return {}
        title = table_inf.get("TITLE", {})
        title_text = title.get("$") if isinstance(title, dict) else title
        statistics_name_spec = table_inf.get("STATISTICS_NAME_SPEC", {})
        return {
            "statistics_name": table_inf.get("STATISTICS_NAME", ""),
            "tabulation_sub_category": (
                statistics_name_spec.get("TABULATION_SUB_CATEGORY1", "")
                if isinstance(statistics_name_spec, dict)
                else ""
            ),
            "title": title_text or "",
            "survey_date": table_inf.get("SURVEY_DATE", ""),
            "open_date": table_inf.get("OPEN_DATE", ""),
            "updated_date": table_inf.get("UPDATED_DATE", ""),
        }

    @staticmethod
    def _extract_class_metadata(response: dict) -> dict:
        class_objects = (
            response.get("GET_STATS_DATA", {})
            .get("STATISTICAL_DATA", {})
            .get("CLASS_INF", {})
            .get("CLASS_OBJ", [])
        )
        if isinstance(class_objects, dict):
            class_objects = [class_objects]

        metadata = {}
        for class_object in class_objects:
            if not isinstance(class_object, dict):
                continue
            class_id = str(class_object.get("@id", ""))
            classes = class_object.get("CLASS", [])
            if isinstance(classes, dict):
                classes = [classes]
            metadata[class_id] = {
                str(item.get("@code")): {
                    "name": item.get("@name", ""),
                    "unit": item.get("@unit", ""),
                }
                for item in classes
                if isinstance(item, dict) and item.get("@code")
            }
        return metadata

    @classmethod
    def _build_cultivated_area_distribution_rows(
        cls, area_snapshots_by_period: dict, count_snapshots_by_period: dict
    ) -> list[dict[str, float | str | None]]:
        """
        面積表と経営体数表を規模区分ラベルで突き合わせた分布行を作ります。

        e-Stat では面積表と経営体数表で cat02 コードの並びが一致しないため、
        コードではなく分類名を正規化して結合します。
        """
        total_snapshot = area_snapshots_by_period.get("1001")
        total_value = total_snapshot.value if total_snapshot is not None else None
        count_snapshots_by_label = cls._snapshots_by_normalized_label(
            count_snapshots_by_period
        )
        rows = []
        for period_label in cls._distribution_period_labels(area_snapshots_by_period):
            snapshot = area_snapshots_by_period.get(period_label)
            value = snapshot.value if snapshot is not None else None
            label = cls._distribution_label(snapshot, period_label)
            count_snapshot = count_snapshots_by_label.get(
                cls._normalize_scale_label(label)
            )
            rows.append(
                {
                    "label": label,
                    "period_label": period_label,
                    "value": value,
                    "unit": "ha",
                    "share": AgriculturalRiskCalculator._ratio(value, total_value),
                    "count_value": (
                        count_snapshot.value if count_snapshot is not None else None
                    ),
                    "count_unit": (
                        count_snapshot.dataset.unit
                        if count_snapshot is not None
                        else "経営体"
                    ),
                }
            )
        return rows

    @staticmethod
    def _build_cultivated_area_distribution_summary(
        rows: list[dict[str, float | str | None]],
    ) -> dict[str, float | str | None]:
        total_row = next(
            (row for row in rows if row.get("period_label") == "1001"),
            None,
        )
        if total_row is None:
            return {}
        return total_row

    @classmethod
    def _distribution_period_labels(cls, snapshots_by_period: dict) -> list[str]:
        if snapshots_by_period:
            return list(snapshots_by_period.keys())
        return list(CULTIVATED_AREA_DISTRIBUTION_FALLBACK_LABELS.keys())

    @classmethod
    def _snapshots_by_normalized_label(cls, snapshots_by_period: dict) -> dict:
        return {
            cls._normalize_scale_label(
                cls._distribution_label(snapshot, period_label)
            ): snapshot
            for period_label, snapshot in snapshots_by_period.items()
        }

    @classmethod
    def _distribution_label(cls, snapshot, period_label: str) -> str:
        if snapshot is not None:
            class_metadata = snapshot.raw_data.get("_class_metadata", {})
            cat02_metadata = (
                class_metadata.get("cat02", {})
                if isinstance(class_metadata, dict)
                else {}
            )
            code_metadata = cat02_metadata.get(str(period_label), {})
            name = code_metadata.get("name") if isinstance(code_metadata, dict) else ""
            if name:
                return cls._format_scale_label(name)
        return CULTIVATED_AREA_DISTRIBUTION_FALLBACK_LABELS.get(
            period_label, period_label
        )

    @staticmethod
    def _format_scale_label(label: str) -> str:
        if label in {"計", "経営耕地なし"}:
            return label
        if "ha" in label:
            return label
        return f"{label}ha"

    @staticmethod
    def _normalize_scale_label(label: str) -> str:
        return label.replace("ha", "")

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
    def _build_risk_input(
        cls,
        latest: dict,
        distribution_snapshots: dict | None = None,
        successor_snapshots: dict | None = None,
    ) -> AgriculturalRiskInput:
        return AgriculturalRiskInput(
            total_cultivated_area=(
                cls._value(latest, "total_cultivated_area")
                or cls._distribution_total_value(distribution_snapshots or {})
            ),
            age_70_plus_area=cls._value(latest, "age_70_plus_area"),
            age_60s_area=cls._value(latest, "age_60s_area"),
            no_successor_ratio=(
                cls._ratio_value(latest, "no_successor_ratio")
                or cls._successor_missing_ratio(successor_snapshots or {})
            ),
            shrink_stop_intention_ratio=cls._ratio_value(
                latest, "shrink_stop_intention_ratio"
            ),
            supplemental_unmanageable_area=cls._value(
                latest, ABANDONED_FARMLAND_AREA_KEY
            )
            or 0.0,
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
    def _distribution_total_value(distribution_snapshots: dict) -> float | None:
        total_snapshot = distribution_snapshots.get("1001")
        if total_snapshot is None:
            return None
        return total_snapshot.value

    @staticmethod
    def _successor_missing_ratio(
        snapshots_by_period: dict,
    ) -> float | None:
        """
        `successor_missing` は農業経営の後継者が未確保である状態を指します。

        農業経営の後継者を確保していない経営体の割合を算出します。

        2020年農林業センサスの「5年以内の後継者の確保状況別経営体数」では、
        period_label `1001` が経営体数の計、`1007` が「後継者を確保していない」
        経営体数です。この2値から `no_successor_ratio` の代替値を作ります。

        Args:
            snapshots_by_period: 後継者確保状況の分類コードをキーにした統計値。

        Returns:
            「後継者を確保していない経営体数 / 計」の比率。必要な分類値が
            欠けている場合や計が0の場合は None。
        """
        total_snapshot = snapshots_by_period.get("1001")
        missing_snapshot = snapshots_by_period.get("1007")
        total = total_snapshot.value if total_snapshot is not None else None
        missing = missing_snapshot.value if missing_snapshot is not None else None
        if not total:
            return None
        if missing is None:
            return None
        return missing / total

    @classmethod
    def _build_age_group_rows(
        cls, age_snapshots_by_period: dict
    ) -> list[dict[str, float | str | None]]:
        """
        経営主年齢の分類を画面用の年齢階級へ集約します。

        e-Stat上の細かい年齢階層を、30歳未満、30代、40代、50代、
        60代、70歳以上にまとめ、男女別や「男女計」接頭辞を出さずに見せます。
        """
        if age_snapshots_by_period:
            total_snapshot = age_snapshots_by_period.get("1001")
            total = total_snapshot.value if total_snapshot is not None else None
            rows = []
            data_period_label = None
            if total_snapshot is not None:
                data_period_label = cls._data_period_label(total_snapshot)
            for label, codes in OPERATOR_AGE_GROUP_CODES.items():
                value = cls._sum_values_for_period_labels(
                    age_snapshots_by_period, codes
                )
                rows.append(
                    {
                        "label": label,
                        "value": value,
                        "unit": "経営体",
                        "share": AgriculturalRiskCalculator._ratio(value, total),
                        "data_period_label": data_period_label,
                    }
                )
            return rows
        return []

    @staticmethod
    def _sum_values_for_period_labels(
        snapshots_by_period: dict, period_labels: set[str]
    ) -> float | None:
        """
        指定した分類コードに対応する e-Stat 統計値を合計します。

        ここでの `period_label` は時系列の期間ではなく、e-Stat の分類コードです。
        例えば経営主年齢の 30代 は、30〜34歳と35〜39歳の2つの分類コードを
        1つの表示行へまとめるため、このメソッドで各分類の値を足します。

        Args:
            snapshots_by_period: e-Stat の分類コードをキーにした保存済み統計値。
            period_labels: 合計対象にする分類コードの集合。

        Returns:
            合計値。対象分類が存在しない、または値がすべて欠けている場合は None。
        """
        values = [
            snapshots_by_period[period_label].value
            for period_label in period_labels
            if period_label in snapshots_by_period
            and snapshots_by_period[period_label].value is not None
        ]
        if not values:
            return None
        return sum(values)

    @classmethod
    def _build_classification_rows(
        cls,
        snapshots_by_period: dict,
        skip_total: bool = False,
        skip_subtotal: bool = False,
    ) -> list[dict[str, float | str | None]]:
        """
        分類コード別の統計値を画面表示用の行へ変換します。

        `skip_total` は年齢階層表のように「計」を表から外しつつ、構成比の母数には
        使いたい場合に指定します。
        """
        total_snapshot = snapshots_by_period.get("1001")
        total_value = total_snapshot.value if total_snapshot is not None else None
        rows = []
        for period_label, snapshot in snapshots_by_period.items():
            if skip_total and period_label == "1001":
                continue
            label = cls._class_label(snapshot, period_label, "cat02")
            if skip_subtotal and "小計" in label:
                continue
            value = snapshot.value if snapshot is not None else None
            rows.append(
                {
                    "label": label,
                    "period_label": period_label,
                    "value": value,
                    "unit": snapshot.dataset.unit if snapshot is not None else "",
                    "share": AgriculturalRiskCalculator._ratio(value, total_value),
                    "data_period_label": (
                        cls._data_period_label(snapshot)
                        if snapshot is not None
                        else None
                    ),
                }
            )
        return rows

    @classmethod
    def _build_dataset_status_rows(
        cls,
        datasets: list,
        latest_snapshot_values: dict,
        distribution_snapshots: dict | None = None,
    ) -> list[EstatDatasetStatus]:
        return [
            cls._build_dataset_status_row(
                dataset, latest_snapshot_values, distribution_snapshots or {}
            )
            for dataset in datasets
        ]

    @classmethod
    def _build_dataset_status_row(
        cls, dataset, latest_snapshot_values: dict, distribution_snapshots: dict
    ) -> EstatDatasetStatus:
        snapshot = cls._status_snapshot(
            dataset, latest_snapshot_values, distribution_snapshots
        )
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
            data_period_label=(
                cls._data_period_label(snapshot) if snapshot is not None else None
            ),
            fetched_at=snapshot.fetched_at if snapshot is not None else None,
            estat_updated_at=(
                snapshot.estat_updated_at if snapshot is not None else None
            ),
        )

    @staticmethod
    def _fetch_target_datasets(datasets: list) -> list:
        return [
            dataset
            for dataset in datasets
            if dataset.indicator_key
            not in DERIVED_INDICATOR_KEYS | CALCULATION_ONLY_INDICATOR_KEYS
        ]

    @staticmethod
    def _display_datasets(datasets: list) -> list:
        return sorted(
            [
                dataset
                for dataset in datasets
                if dataset.indicator_key
                not in DERIVED_INDICATOR_KEYS | CALCULATION_ONLY_INDICATOR_KEYS
            ],
            key=lambda dataset: (
                dataset.stats_data_id.startswith("TODO_"),
                dataset.stats_data_id,
                dataset.display_name,
            ),
        )

    @staticmethod
    def _status_snapshot(
        dataset, latest_snapshot_values: dict, distribution_snapshots: dict
    ):
        if dataset.indicator_key == CULTIVATED_AREA_DISTRIBUTION_KEY:
            return distribution_snapshots.get("1001") or latest_snapshot_values.get(
                dataset.indicator_key
            )
        return latest_snapshot_values.get(dataset.indicator_key)

    @staticmethod
    def _class_label(snapshot, period_label: str, class_id: str) -> str:
        if snapshot is not None:
            class_metadata = snapshot.raw_data.get("_class_metadata", {})
            metadata = (
                class_metadata.get(class_id, {})
                if isinstance(class_metadata, dict)
                else {}
            )
            code_metadata = metadata.get(str(period_label), {})
            name = code_metadata.get("name") if isinstance(code_metadata, dict) else ""
            if name:
                return name
        return period_label

    @staticmethod
    def _source_page_url(stats_data_id: str) -> str:
        return f"{ESTAT_DATA_VIEW_URL}?sid={stats_data_id}"

    @staticmethod
    def _filters_label(filters: dict) -> str:
        if not filters:
            return "なし"
        return ", ".join(f"{key}={value}" for key, value in sorted(filters.items()))

    @classmethod
    def _data_period_label(cls, snapshot) -> str | None:
        metadata = snapshot.raw_data.get("_table_metadata", {})
        survey_date = metadata.get("survey_date") if isinstance(metadata, dict) else ""
        if survey_date:
            formatted_survey_date = cls._format_survey_date(survey_date)
            tabulation_name = metadata.get("tabulation_sub_category", "")
            if tabulation_name:
                return f"{tabulation_name}（{formatted_survey_date}）"
            return formatted_survey_date
        if snapshot.raw_data.get("@time"):
            return str(snapshot.raw_data["@time"])
        return cls._fallback_data_period_label(snapshot.dataset)

    @staticmethod
    def _fallback_data_period_label(dataset) -> str | None:
        for definition in DEFAULT_ESTAT_DATASETS:
            if definition["indicator_key"] == dataset.indicator_key:
                return definition.get("fallback_data_period_label")
        return None

    @staticmethod
    def _format_survey_date(survey_date: str) -> str:
        if len(survey_date) == 13 and survey_date[6] == "-":
            start = survey_date[:6]
            end = survey_date[7:]
            return (
                f"{int(start[:4])}年{int(start[4:])}月"
                f"〜{int(end[:4])}年{int(end[4:])}月"
            )
        if len(survey_date) == 6:
            return f"{int(survey_date[:4])}年{int(survey_date[4:])}月"
        return survey_date

    @staticmethod
    def _distribution_source_rows(
        rows: list[EstatDatasetStatus],
    ) -> list[EstatDatasetStatus]:
        return [
            row
            for row in rows
            if row.indicator_key
            in {
                CULTIVATED_AREA_DISTRIBUTION_KEY,
                CULTIVATED_AREA_DISTRIBUTION_COUNT_KEY,
            }
            and row.status_label == "取得済み"
        ]

    @staticmethod
    def _build_supplemental_indicator_rows(
        indicators: list,
    ) -> list[SupplementalRiskIndicatorStatus]:
        return [
            SupplementalRiskIndicatorStatus(
                indicator_key=indicator.indicator_key,
                display_name=indicator.display_name,
                source_name=indicator.source_name,
                source_url=indicator.source_url,
                region_label=indicator.region_label,
                period_label=indicator.period_label,
                value=indicator.value,
                unit=indicator.unit,
                category=indicator.category,
                note=indicator.note,
            )
            for indicator in indicators
        ]

    @staticmethod
    def _build_inheritance_land_reversion_summary(
        rows: list[SupplementalRiskIndicatorStatus],
    ) -> dict:
        """
        相続土地国庫帰属制度の全国値を合計と内訳に分けます。

        法務省ページの同一ソースにある値なので、別々のカードではなく合計値と
        補足内訳として表示できる形へ整えます。
        """
        target_rows = [
            row for row in rows if row.category == "inheritance_land_reversion"
        ]
        total = next(
            (
                row
                for row in target_rows
                if row.indicator_key == INHERITANCE_LAND_REVERSION_TOTAL_KEY
            ),
            None,
        )
        rows_by_key = {row.indicator_key: row for row in target_rows}
        application_rows = [
            rows_by_key[indicator_key]
            for indicator_key in INHERITANCE_LAND_REVERSION_APPLICATION_KEYS
            if indicator_key in rows_by_key
        ]
        supplemental_rows = [
            row
            for row in target_rows
            if row.indicator_key
            not in {INHERITANCE_LAND_REVERSION_TOTAL_KEY}
            | set(INHERITANCE_LAND_REVERSION_APPLICATION_KEYS)
        ]
        return {
            "total": total,
            "application_breakdown_rows": application_rows,
            "supplemental_rows": supplemental_rows,
            "trend_note": "現時点では法務省ページ上の最新累計値のみを表示しています。今後、月次の過去値を保存できるようにするとトレンド化できます。",
        }

    @staticmethod
    def _build_kpi_basis(rows: list[EstatDatasetStatus]) -> dict:
        """
        KPIカードに表示するデータ根拠を指標取得状況から組み立てます。

        画面上で六戸町値と全国値、2020年/2015年などの時点が混ざらないよう、
        KPIごとに地域粒度とデータ時点を明示します。
        """
        status_by_key = {row.indicator_key: row for row in rows}
        base = status_by_key.get(CULTIVATED_AREA_DISTRIBUTION_KEY)
        age = status_by_key.get(OPERATOR_AGE_DISTRIBUTION_KEY)
        successor = status_by_key.get(SUCCESSOR_STATUS_DISTRIBUTION_KEY)
        abandoned = status_by_key.get(ABANDONED_FARMLAND_AREA_KEY)
        base_period = base.data_period_label if base is not None else None
        age_period = age.data_period_label if age is not None else None
        successor_period = (
            successor.data_period_label if successor is not None else None
        )
        abandoned_period = (
            abandoned.data_period_label if abandoned is not None else None
        )
        return {
            "unmanageable_candidate_area": {
                "region_label": "六戸町",
                "period_label": abandoned_period or "-",
                "source_label": "耕作放棄地面積",
            },
            "farmland_maintenance_rate": {
                "region_label": "六戸町",
                "period_label": f"母数: {base_period or '-'}",
                "source_label": "経営耕地面積と管理不能化候補面積",
            },
            "succession_risk": {
                "region_label": "六戸町",
                "period_label": successor_period or "-",
                "source_label": "後継者を確保していない経営体数 / 計",
            },
            "operator_age_distribution": {
                "region_label": "六戸町",
                "period_label": age_period or "-",
                "source_label": age.display_name if age is not None else "",
                "stats_data_id": age.stats_data_id if age is not None else "",
                "source_page_url": age.source_page_url if age is not None else "",
            },
            "intention_risk": {
                "region_label": "未設定",
                "period_label": "-",
                "source_label": "e-Statで直接取得できる経営意向データは未確定",
            },
            "risk_breakdown": {
                "region_label": "六戸町",
                "period_label": f"後継者: {successor_period or '-'} / 耕作放棄地: {abandoned_period or '-'}",
                "source_label": "農林業センサス由来の補助統計",
            },
        }
