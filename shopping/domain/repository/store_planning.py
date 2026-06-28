from django.utils import timezone

from shopping.domain.valueobject.store_planning import (
    STORE_PLANNING_TARGET_LOCATIONS,
    StorePlanningDataSource,
)
from shopping.models import StorePlanningDataSourceSnapshot


class StorePlanningDataSourceRepository:
    """出店計画で使う e-Stat 人口CSVの集計結果を保存・参照する。"""

    ACTIVE_SOURCE_KEYS = [
        location.source_key for location in STORE_PLANNING_TARGET_LOCATIONS
    ]

    @staticmethod
    def save_snapshot(
        data_source: StorePlanningDataSource,
    ) -> StorePlanningDataSourceSnapshot:
        snapshot, _ = StorePlanningDataSourceSnapshot.objects.update_or_create(
            source_key=data_source.source_key,
            defaults={
                "display_name": data_source.display_name,
                "source_url": data_source.source_url,
                "status": data_source.status,
                "data_period": data_source.data_period,
                "source_updated_at": data_source.source_updated_at,
                "fetched_at": timezone.now(),
                "raw_data": data_source.raw_data,
            },
        )
        return snapshot

    @staticmethod
    def list_latest() -> list[StorePlanningDataSourceSnapshot]:
        return list(
            StorePlanningDataSourceSnapshot.objects.filter(
                source_key__in=StorePlanningDataSourceRepository.ACTIVE_SOURCE_KEYS
            ).order_by("source_key")
        )

    @staticmethod
    def get_latest_by_source_key(
        source_key: str,
    ) -> StorePlanningDataSourceSnapshot | None:
        return StorePlanningDataSourceSnapshot.objects.filter(
            source_key=source_key
        ).first()
