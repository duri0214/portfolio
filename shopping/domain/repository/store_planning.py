from django.db import transaction
from django.utils import timezone

from shopping.domain.valueobject.store_planning import (
    AREA_HIERARCHY_LEVEL_BLOCK,
    AREA_HIERARCHY_LEVEL_CITY,
    AREA_HIERARCHY_LEVEL_PARENT_TOWN,
    StorePlanningDataSource,
    StorePlanningTargetLocation,
)
from shopping.models import StorePlanningDataSourceSnapshot, StorePlanningTargetStore


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
        """
        e-Stat人口CSVの保存済み明細から、地域階層レベル1の市区町村範囲を集計する。

        地域階層レベルは総務省統計局「令和2年国勢調査 調査結果の利用案内」
        に示されるCSV上の固定的な区分値で、アプリ側で増減させる計算値ではない。
        ここでは表示用のカバー範囲として、地域階層レベル1のraw_dataに含まれる
        都道府県名・市区町村名を列挙し、地域階層レベル別の明細数だけを添える。
        """
        raw_data_rows = StorePlanningDataSourceSnapshot.objects.values_list(
            "raw_data", flat=True
        )
        prefectures = set()
        cities = set()
        area_hierarchy_level_counts = {}
        fetched_at = None
        for raw_data in raw_data_rows:
            prefecture_name = raw_data.get("prefecture_name")
            city_name = raw_data.get("city_name")
            city_code = raw_data.get("city_code")
            area_hierarchy_level = raw_data.get("area_hierarchy_level")
            if prefecture_name:
                prefectures.add(prefecture_name)
            if (
                area_hierarchy_level == AREA_HIERARCHY_LEVEL_CITY
                and city_code
                and city_name
            ):
                cities.add((prefecture_name or "", city_code, city_name))
            if city_code and area_hierarchy_level:
                area_hierarchy_level_counts[area_hierarchy_level] = (
                    area_hierarchy_level_counts.get(area_hierarchy_level, 0) + 1
                )

        latest_snapshot = StorePlanningDataSourceSnapshot.objects.order_by(
            "-fetched_at"
        ).first()
        if latest_snapshot is not None:
            fetched_at = latest_snapshot.fetched_at

        return {
            "prefecture_names": sorted(prefectures),
            "city_count": len(cities),
            "town_count": area_hierarchy_level_counts.get(
                AREA_HIERARCHY_LEVEL_BLOCK, 0
            ),
            "area_hierarchy_level_counts": dict(
                sorted(area_hierarchy_level_counts.items())
            ),
            "city_rows": [
                {
                    "prefecture_name": prefecture_name,
                    "city_code": city_code,
                    "city_name": city_name,
                }
                for prefecture_name, city_code, city_name in sorted(cities)
            ],
            "fetched_at": fetched_at,
        }

    @staticmethod
    def find_nearby_area_candidate_snapshots(
        city_code: str,
        town_code: str,
        limit: int = 6,
    ) -> list[StorePlanningDataSourceSnapshot]:
        """
        e-Stat CSVの地域コードから、比較候補になる町丁を取得する。

        境界ポリゴンを使った接触判定ではなく、同じ市区町村かつ
        字・丁目単位を表す地域階層レベル4、町丁字コードの先頭ゼロを除いた
        先頭2桁が一致する地域を候補として返す。
        e-Stat CSV上の町丁字コードは先頭ゼロ付きで保存される場合があるため、
        比較キーだけを正規化し、DB検索では保存形式に合わせたprefixを使う。
        引数の町丁字コードも町丁リストのrootとして含め、画面側で選択中の
        地域として強調する。
        """
        town_code_prefix = StorePlanningDataSourceRepository._town_code_prefix(
            town_code
        )
        snapshots = StorePlanningDataSourceSnapshot.objects.filter(
            raw_data__city_code=city_code,
            raw_data__area_hierarchy_level=AREA_HIERARCHY_LEVEL_BLOCK,
            raw_data__town_code__startswith=town_code_prefix,
        ).order_by("source_key")
        return list(snapshots[:limit])

    @staticmethod
    def get_parent_area_snapshot(
        city_code: str, town_code: str
    ) -> StorePlanningDataSourceSnapshot | None:
        """
        町丁字コードから地域階層レベル3の親地域を取得する。

        例として、東保木間二丁目の町丁字コード `073002` から、
        大字・町名が同じ字・丁目の合計を表す `0730` を取得する。
        """
        parent_town_code = StorePlanningDataSourceRepository._parent_town_code(
            town_code
        )
        return StorePlanningDataSourceSnapshot.objects.filter(
            raw_data__city_code=city_code,
            raw_data__area_hierarchy_level=AREA_HIERARCHY_LEVEL_PARENT_TOWN,
            raw_data__town_code=parent_town_code,
        ).first()

    @staticmethod
    def _town_code_prefix(town_code: str) -> str:
        stripped_code = town_code.lstrip("0")
        if not stripped_code:
            return town_code[:2]
        prefix_length = len(town_code) - len(stripped_code) + 2
        return town_code[:prefix_length]

    @staticmethod
    def _parent_town_code(town_code: str) -> str:
        return town_code[:4]


class StorePlanningTargetStoreRepository:
    """出店計画画面で選択するサンプル店舗候補を参照する。"""

    @classmethod
    def get_active_locations(cls) -> list[StorePlanningTargetLocation]:
        stores = StorePlanningTargetStore.objects.filter(is_active=True)
        return [cls._to_location(store) for store in stores]

    @classmethod
    def _to_location(
        cls, store: StorePlanningTargetStore
    ) -> StorePlanningTargetLocation:
        return StorePlanningTargetLocation(
            slug=store.slug,
            name=store.name,
            address=store.address,
            latitude=store.latitude,
            longitude=store.longitude,
            city_code=store.city_code,
            town_code=store.town_code,
            population_area=store.population_area,
            large_area_name=store.large_area_name,
            small_area_name=store.small_area_name,
            area_hierarchy_level=store.area_hierarchy_level,
        )
