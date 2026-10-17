"""土壌図データ版とPolygonの永続化を扱うリポジトリ。"""

from django.db.models import Count

from soil_analysis.models import SoilMapDataset, SoilMapPolygon


class SoilMapRepository:
    """土壌図の取込と表示に必要なDB操作を集約する。"""

    @staticmethod
    def zip_file_exists(source_sha256: str) -> bool:
        """同じZIPがすでに取り込まれているかを返す。"""
        return SoilMapDataset.objects.filter(source_sha256=source_sha256).exists()

    @staticmethod
    def deactivate_active_datasets() -> None:
        """現在有効な土壌図版を無効化する。"""
        SoilMapDataset.objects.filter(is_active=True).update(is_active=False)

    @staticmethod
    def create_dataset(**values) -> SoilMapDataset:
        """新しい土壌図データ版を保存して返す。"""
        return SoilMapDataset.objects.create(**values)

    @staticmethod
    def bulk_create_polygons(dataset: SoilMapDataset, polygons: list[dict]) -> None:
        """一つのデータ版に属するPolygonをまとめて保存する。"""
        SoilMapPolygon.objects.bulk_create(
            [SoilMapPolygon(dataset=dataset, **polygon) for polygon in polygons],
            batch_size=len(polygons),
        )

    @staticmethod
    def get_active_dataset() -> SoilMapDataset | None:
        """地図表示に使う有効版を返す。"""
        return SoilMapDataset.objects.filter(is_active=True).first()

    @staticmethod
    def get_prefecture_soil_summaries(dataset: SoilMapDataset):
        """都道府県・土壌名ごとのPolygon数を多い順に返す。"""
        return (
            SoilMapPolygon.objects.filter(dataset=dataset)
            .values("prefecture_code", "soil_name", "soil_group_code")
            .annotate(polygon_count=Count("id"))
            .order_by("prefecture_code", "-polygon_count", "soil_name")
        )
