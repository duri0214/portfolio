"""市区町村境界と土壌面積集計の永続化を扱うリポジトリ。"""

from django.db.models import Sum

from soil_analysis.models import (
    MunicipalityBoundary,
    MunicipalityBoundaryDataset,
    MunicipalitySoilAggregation,
    MunicipalitySoilArea,
    SoilMapDataset,
    SoilMapPolygon,
)


class MunicipalitySoilRepository:
    """市区町村別土壌集計に必要なDB操作を集約する。"""

    @staticmethod
    def boundary_zip_file_exists(source_sha256: str) -> bool:
        """同じ境界ZIPがすでに取り込み済みかを返す。"""
        return MunicipalityBoundaryDataset.objects.filter(
            source_sha256=source_sha256
        ).exists()

    @staticmethod
    def deactivate_active_boundary_datasets() -> None:
        """現在有効な市区町村境界版を無効化する。"""
        MunicipalityBoundaryDataset.objects.filter(is_active=True).update(
            is_active=False
        )

    @staticmethod
    def create_boundary_dataset(**values) -> MunicipalityBoundaryDataset:
        """新しい市区町村境界版を保存して返す。"""
        return MunicipalityBoundaryDataset.objects.create(**values)

    @staticmethod
    def bulk_create_municipalities(
        dataset: MunicipalityBoundaryDataset, municipalities: list[dict]
    ) -> None:
        """市区町村境界をまとめて保存する。"""
        MunicipalityBoundary.objects.bulk_create(
            [
                MunicipalityBoundary(dataset=dataset, **municipality)
                for municipality in municipalities
            ],
            batch_size=200,
        )

    @staticmethod
    def get_active_boundary_dataset() -> MunicipalityBoundaryDataset | None:
        """地図表示に使う有効な市区町村境界版を返す。"""
        return MunicipalityBoundaryDataset.objects.filter(is_active=True).first()

    @staticmethod
    def get_active_soil_dataset() -> SoilMapDataset | None:
        """市区町村集計に使う有効な土壌図版を返す。"""
        return SoilMapDataset.objects.filter(is_active=True).first()

    @staticmethod
    def get_municipalities_for_prefecture(
        dataset: MunicipalityBoundaryDataset, prefecture_code: str
    ):
        """指定都道府県に属する市区町村境界を返す。"""
        return MunicipalityBoundary.objects.filter(
            dataset=dataset, prefecture_code=prefecture_code
        ).order_by("municipality_code")

    @staticmethod
    def get_soil_polygons_for_prefecture(dataset: SoilMapDataset, prefecture_code: str):
        """指定都道府県の土壌Polygonを返す。"""
        return SoilMapPolygon.objects.filter(
            dataset=dataset, prefecture_code=prefecture_code
        ).only(
            "coordinates",
            "soil_group_code",
            "soil_subgroup_code",
            "soil_series_code",
            "soil_name",
        )

    @staticmethod
    def delete_aggregations(
        soil_dataset: SoilMapDataset, boundary_dataset: MunicipalityBoundaryDataset
    ) -> None:
        """同じ入力版の既存集計を削除する。"""
        MunicipalitySoilAggregation.objects.filter(
            soil_dataset=soil_dataset, boundary_dataset=boundary_dataset
        ).delete()

    @staticmethod
    def create_aggregation(**values) -> MunicipalitySoilAggregation:
        """市区町村ごとの集計結果を保存する。"""
        return MunicipalitySoilAggregation.objects.create(**values)

    @staticmethod
    def bulk_create_soil_areas(
        aggregation: MunicipalitySoilAggregation, soil_areas: list[dict]
    ) -> None:
        """市区町村の土壌分類別面積をまとめて保存する。"""
        MunicipalitySoilArea.objects.bulk_create(
            [
                MunicipalitySoilArea(aggregation=aggregation, **soil_area)
                for soil_area in soil_areas
            ],
            batch_size=500,
        )

    @staticmethod
    def get_municipality(
        dataset: MunicipalityBoundaryDataset, municipality_code: str
    ) -> MunicipalityBoundary | None:
        """有効境界版の市区町村を返す。"""
        return MunicipalityBoundary.objects.filter(
            dataset=dataset, municipality_code=municipality_code
        ).first()

    @staticmethod
    def get_aggregation(
        soil_dataset: SoilMapDataset,
        boundary_dataset: MunicipalityBoundaryDataset,
        municipality: MunicipalityBoundary,
    ) -> MunicipalitySoilAggregation | None:
        """入力版と市区町村に対応する集計結果を返す。"""
        return MunicipalitySoilAggregation.objects.filter(
            soil_dataset=soil_dataset,
            boundary_dataset=boundary_dataset,
            municipality=municipality,
        ).first()

    @staticmethod
    def get_prefecture_aggregations(
        soil_dataset: SoilMapDataset,
        boundary_dataset: MunicipalityBoundaryDataset,
        prefecture_code: str,
    ):
        """都道府県内の市区町村集計を市区町村コードごとに返す。"""
        return MunicipalitySoilAggregation.objects.filter(
            soil_dataset=soil_dataset,
            boundary_dataset=boundary_dataset,
            municipality__prefecture_code=prefecture_code,
        ).select_related("municipality")

    @staticmethod
    def get_soil_area_rows(aggregation: MunicipalitySoilAggregation):
        """詳細ページ用の土壌分類面積を返す。"""
        return aggregation.soil_areas.all()

    @staticmethod
    def get_soil_area_summaries(
        aggregation: MunicipalitySoilAggregation, fields: list[str]
    ):
        """指定した分類列ごとに面積を合計して返す。"""
        return (
            aggregation.soil_areas.values(*fields)
            .annotate(area_sq_m=Sum("area_sq_m"))
            .order_by("-area_sq_m", *fields)
        )
