from django.db import transaction
from django.utils import timezone

from shopping.domain.valueobject.store_planning import StorePlanningDataSource
from shopping.models import StorePlanningDataSourceSnapshot


class StorePlanningDataSourceRepository:
    """出店計画で使う e-Stat 人口CSVの集計結果を保存・参照する。"""

    @classmethod
    def replace_snapshots(
        cls, data_sources: list[StorePlanningDataSource]
    ) -> list[StorePlanningDataSourceSnapshot]:
        fetched_at = timezone.now()
        snapshots = [
            StorePlanningDataSourceSnapshot(
                source_key=data_source.source_key,
                display_name=data_source.display_name,
                source_url=data_source.source_url,
                status=data_source.status,
                data_period=data_source.data_period,
                source_updated_at=data_source.source_updated_at,
                fetched_at=fetched_at,
                raw_data=data_source.raw_data,
            )
            for data_source in data_sources
        ]
        with transaction.atomic():
            StorePlanningDataSourceSnapshot.objects.all().delete()
            return StorePlanningDataSourceSnapshot.objects.bulk_create(snapshots)

    @staticmethod
    def get_latest_by_source_key(
        source_key: str,
    ) -> StorePlanningDataSourceSnapshot | None:
        return StorePlanningDataSourceSnapshot.objects.filter(
            source_key=source_key
        ).first()

    @staticmethod
    def get_population_csv_coverage() -> dict:
        raw_data_rows = StorePlanningDataSourceSnapshot.objects.values_list(
            "raw_data", flat=True
        )
        prefectures = set()
        cities = set()
        town_count = 0
        fetched_at = None
        for raw_data in raw_data_rows:
            prefecture_name = raw_data.get("prefecture_name")
            city_name = raw_data.get("city_name")
            city_code = raw_data.get("city_code")
            town_code = raw_data.get("town_code")
            if prefecture_name:
                prefectures.add(prefecture_name)
            if city_code and city_name:
                cities.add((city_code, city_name))
            if city_code and town_code:
                town_count += 1

        latest_snapshot = StorePlanningDataSourceSnapshot.objects.order_by(
            "-fetched_at"
        ).first()
        if latest_snapshot is not None:
            fetched_at = latest_snapshot.fetched_at

        return {
            "prefecture_names": sorted(prefectures),
            "city_count": len(cities),
            "town_count": town_count,
            "fetched_at": fetched_at,
        }
