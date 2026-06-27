from datetime import date

from django.db import IntegrityError

from soil_analysis.models import (
    AgriculturalRegion,
    AgriculturalRiskReport,
    AgriculturalStatisticSnapshot,
    EstatDataset,
    SupplementalRiskIndicator,
)


class AgriculturalStatisticsRepository:
    """
    農業統計・離農リスクレポートの永続化を扱うRepositoryです。
    """

    @staticmethod
    def get_or_create_default_region(area_code: str) -> AgriculturalRegion:
        """
        初期対象地域を取得または作成します。

        Args:
            area_code: e-Stat 地域コード。

        Returns:
            AgriculturalRegion: 対象地域。
        """
        defaults_by_area_code = {
            "02405": {
                "name": "上北郡六戸町",
                "prefecture_name": "青森県",
            },
            "00000": {
                "name": "全国",
                "prefecture_name": "",
            },
        }
        defaults = defaults_by_area_code.get(
            area_code,
            {
                "name": area_code,
                "prefecture_name": "",
            },
        )
        region, _ = AgriculturalRegion.objects.get_or_create(
            area_code=area_code,
            defaults=defaults,
        )
        return region

    @staticmethod
    def upsert_dataset(definition: dict) -> EstatDataset:
        """
        指標定義を取得または更新します。

        Args:
            definition: 指標定義。

        Returns:
            EstatDataset: 保存済み指標定義。
        """
        dataset, _ = EstatDataset.objects.update_or_create(
            indicator_key=definition["indicator_key"],
            defaults={
                "display_name": definition["display_name"],
                "stats_data_id": definition["stats_data_id"],
                "filters": definition.get("filters", {}),
                "unit": definition.get("unit", ""),
                "category": definition.get("category", ""),
            },
        )
        return dataset

    @staticmethod
    def ensure_dataset(definition: dict) -> EstatDataset:
        """
        指標定義を取得し、未作成または TODO 状態の場合だけ初期値を反映します。

        Args:
            definition: 指標定義。

        Returns:
            EstatDataset: 保存済み指標定義。
        """
        defaults = {
            "display_name": definition["display_name"],
            "stats_data_id": definition["stats_data_id"],
            "filters": definition.get("filters", {}),
            "unit": definition.get("unit", ""),
            "category": definition.get("category", ""),
        }
        dataset, created = EstatDataset.objects.get_or_create(
            indicator_key=definition["indicator_key"],
            defaults=defaults,
        )
        if not created and dataset.stats_data_id.startswith("TODO_"):
            for field, value in defaults.items():
                setattr(dataset, field, value)
            dataset.save(update_fields=[*defaults.keys(), "updated_at"])
        return dataset

    @staticmethod
    def upsert_supplemental_indicator(definition: dict) -> SupplementalRiskIndicator:
        """
        補助指標を取得または更新します。

        Args:
            definition: 補助指標定義。

        Returns:
            SupplementalRiskIndicator: 保存済み補助指標。
        """
        indicator, _ = SupplementalRiskIndicator.objects.update_or_create(
            indicator_key=definition["indicator_key"],
            defaults={
                "display_name": definition["display_name"],
                "source_name": definition["source_name"],
                "source_url": definition["source_url"],
                "region_label": definition["region_label"],
                "period_label": definition["period_label"],
                "value": definition.get("value"),
                "unit": definition.get("unit", ""),
                "category": definition.get("category", ""),
                "note": definition.get("note", ""),
            },
        )
        return indicator

    @staticmethod
    def get_datasets() -> list[EstatDataset]:
        return list(EstatDataset.objects.all().order_by("indicator_key"))

    @staticmethod
    def get_supplemental_indicators() -> list[SupplementalRiskIndicator]:
        return list(SupplementalRiskIndicator.objects.all().order_by("category", "id"))

    @staticmethod
    def get_region_by_area_code(area_code: str) -> AgriculturalRegion:
        return AgriculturalRegion.objects.get(area_code=area_code)

    @staticmethod
    def save_snapshot(
        *,
        region: AgriculturalRegion,
        dataset: EstatDataset,
        period_label: str,
        value: float | None,
        fetched_at,
        estat_updated_at,
        raw_data: dict,
        source_hash: str,
        force: bool = False,
    ) -> tuple[AgriculturalStatisticSnapshot, bool]:
        """
        統計値スナップショットを保存します。

        Args:
            region: 対象地域。
            dataset: 指標定義。
            period_label: 対象期間。
            value: 統計値。
            fetched_at: 取得日時。
            estat_updated_at: e-Stat更新日時。
            raw_data: e-Stat VALUE レコード。
            source_hash: 重複判定ハッシュ。
            force: True の場合はハッシュ末尾に取得日時を加えて保存する。

        Returns:
            tuple[AgriculturalStatisticSnapshot, bool]: スナップショットと新規作成有無。
        """
        effective_hash = (
            f"{source_hash[:40]}-{fetched_at.strftime('%Y%m%d%H%M%S')}"
            if force
            else source_hash
        )
        try:
            return AgriculturalStatisticSnapshot.objects.get_or_create(
                region=region,
                dataset=dataset,
                period_label=period_label,
                source_hash=effective_hash,
                defaults={
                    "value": value,
                    "fetched_at": fetched_at,
                    "estat_updated_at": estat_updated_at,
                    "raw_data": raw_data,
                },
            )
        except IntegrityError:
            snapshot = AgriculturalStatisticSnapshot.objects.get(
                region=region,
                dataset=dataset,
                period_label=period_label,
                source_hash=effective_hash,
            )
            return snapshot, False

    @staticmethod
    def get_latest_snapshot_values(
        region: AgriculturalRegion,
    ) -> dict[str, AgriculturalStatisticSnapshot]:
        snapshots = (
            AgriculturalStatisticSnapshot.objects.filter(region=region)
            .select_related("dataset")
            .order_by("dataset__indicator_key", "-fetched_at", "-id")
        )
        latest = {}
        for snapshot in snapshots:
            key = snapshot.dataset.indicator_key
            if key not in latest:
                latest[key] = snapshot
        return latest

    @staticmethod
    def get_latest_snapshots_by_period(
        region: AgriculturalRegion, indicator_key: str
    ) -> dict[str, AgriculturalStatisticSnapshot]:
        snapshots = (
            AgriculturalStatisticSnapshot.objects.filter(
                region=region,
                dataset__indicator_key=indicator_key,
            )
            .select_related("dataset")
            .order_by("period_label", "-fetched_at", "-id")
        )
        latest = {}
        for snapshot in snapshots:
            if snapshot.period_label not in latest:
                latest[snapshot.period_label] = snapshot
        return latest

    @staticmethod
    def get_snapshots(
        region: AgriculturalRegion,
    ) -> list[AgriculturalStatisticSnapshot]:
        return list(
            AgriculturalStatisticSnapshot.objects.filter(region=region)
            .select_related("dataset")
            .order_by("-fetched_at", "dataset__indicator_key")[:100]
        )

    @staticmethod
    def save_risk_report(
        *,
        region: AgriculturalRegion,
        report_date: date,
        values: dict,
    ) -> AgriculturalRiskReport:
        report, _ = AgriculturalRiskReport.objects.update_or_create(
            region=region,
            report_date=report_date,
            defaults=values,
        )
        return report

    @staticmethod
    def get_latest_risk_report(
        region: AgriculturalRegion,
    ) -> AgriculturalRiskReport | None:
        return AgriculturalRiskReport.objects.filter(region=region).first()

    @staticmethod
    def get_risk_report_trend(
        region: AgriculturalRegion,
    ) -> list[AgriculturalRiskReport]:
        return list(AgriculturalRiskReport.objects.filter(region=region)[:30])
