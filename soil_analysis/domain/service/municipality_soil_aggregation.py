"""市区町村境界と全国土壌図の交差面積を算出するサービス。"""

from collections import defaultdict

from django.db import transaction
from django.utils import timezone
from pyproj import Transformer
from shapely import STRtree, make_valid
from shapely.geometry import LinearRing, MultiPolygon, Polygon, shape
from shapely.ops import transform

from soil_analysis.domain.repository.municipality_soil import (
    MunicipalitySoilRepository,
)
from soil_analysis.domain.service.prefecture_commercial_area import (
    JAPAN_MAP_PREFECTURES,
)
from soil_analysis.models import MunicipalityBoundaryDataset, SoilMapDataset


class MunicipalitySoilAggregationError(Exception):
    """市区町村別土壌面積を算出できない場合のエラー。"""


class MunicipalitySoilAggregationService:
    """等積投影上で土壌Polygonと市区町村境界の交差面積を集計する。"""

    AREA_CRS = "EPSG:6933"
    SOIL_CRS = "EPSG:4612"
    BOUNDARY_CRS = "EPSG:6668"

    @classmethod
    def recalculate_active_datasets(cls) -> int:
        """有効な土壌図版と行政区域版の全市区町村集計を再作成する。"""
        soil_dataset = MunicipalitySoilRepository.get_active_soil_dataset()
        boundary_dataset = MunicipalitySoilRepository.get_active_boundary_dataset()
        if not soil_dataset:
            raise MunicipalitySoilAggregationError("有効な全国土壌図がありません。")
        if not boundary_dataset:
            raise MunicipalitySoilAggregationError(
                "有効な市区町村境界データがありません。"
            )
        return cls.recalculate(soil_dataset, boundary_dataset)

    @classmethod
    def recalculate(
        cls, soil_dataset: SoilMapDataset, boundary_dataset: MunicipalityBoundaryDataset
    ) -> int:
        """指定した入力版の市区町村別土壌面積を再作成する。"""
        soil_transformer = Transformer.from_crs(
            cls.SOIL_CRS, cls.AREA_CRS, always_xy=True
        )
        boundary_transformer = Transformer.from_crs(
            cls.BOUNDARY_CRS, cls.AREA_CRS, always_xy=True
        )
        results = []
        for prefecture_code, _ in JAPAN_MAP_PREFECTURES:
            results.extend(
                cls._calculate_prefecture(
                    soil_dataset,
                    boundary_dataset,
                    f"{prefecture_code:02d}",
                    soil_transformer,
                    boundary_transformer,
                )
            )

        with transaction.atomic():
            MunicipalitySoilRepository.delete_aggregations(
                soil_dataset, boundary_dataset
            )
            for result in results:
                aggregation = MunicipalitySoilRepository.create_aggregation(
                    soil_dataset=soil_dataset,
                    boundary_dataset=boundary_dataset,
                    municipality=result["municipality"],
                    municipality_area_sq_m=result["municipality_area_sq_m"],
                    classified_area_sq_m=result["classified_area_sq_m"],
                    unclassified_area_sq_m=result["unclassified_area_sq_m"],
                    calculated_at=timezone.now(),
                )
                MunicipalitySoilRepository.bulk_create_soil_areas(
                    aggregation, result["soil_areas"]
                )
        return len(results)

    @classmethod
    def _calculate_prefecture(
        cls,
        soil_dataset: SoilMapDataset,
        boundary_dataset: MunicipalityBoundaryDataset,
        prefecture_code: str,
        soil_transformer: Transformer,
        boundary_transformer: Transformer,
    ) -> list[dict]:
        municipalities = list(
            MunicipalitySoilRepository.get_municipalities_for_prefecture(
                boundary_dataset, prefecture_code
            )
        )
        soil_records = list(
            MunicipalitySoilRepository.get_soil_polygons_for_prefecture(
                soil_dataset, prefecture_code
            )
        )
        if not municipalities:
            raise MunicipalitySoilAggregationError(
                f"都道府県コード{prefecture_code}の市区町村境界がありません。"
            )
        if not soil_records:
            raise MunicipalitySoilAggregationError(
                f"都道府県コード{prefecture_code}の土壌図がありません。"
            )

        soil_geometries = [
            cls._soil_to_area_geometry(record.coordinates, soil_transformer)
            for record in soil_records
        ]
        tree = STRtree(soil_geometries)
        results = []
        for municipality in municipalities:
            municipality_geometry = cls._to_area_geometry(
                {"type": "MultiPolygon", "coordinates": municipality.coordinates},
                boundary_transformer,
            )
            if municipality_geometry.is_empty:
                raise MunicipalitySoilAggregationError(
                    f"{municipality.name}の市区町村境界が空です。"
                )
            areas_by_soil = defaultdict(float)
            for index in tree.query(municipality_geometry, predicate="intersects"):
                soil_geometry = soil_geometries[index]
                intersection = municipality_geometry.intersection(soil_geometry)
                if intersection.is_empty or intersection.area <= 0:
                    continue
                soil_record = soil_records[index]
                soil_key = (
                    soil_record.soil_group_code,
                    soil_record.soil_subgroup_code,
                    soil_record.soil_series_code,
                    soil_record.soil_name,
                )
                areas_by_soil[soil_key] += intersection.area
            classified_area = sum(areas_by_soil.values())
            municipality_area = municipality_geometry.area
            results.append(
                {
                    "municipality": municipality,
                    "municipality_area_sq_m": municipality_area,
                    "classified_area_sq_m": classified_area,
                    "unclassified_area_sq_m": max(
                        municipality_area - classified_area, 0
                    ),
                    "soil_areas": [
                        {
                            "soil_group_code": soil_group_code,
                            "soil_subgroup_code": soil_subgroup_code,
                            "soil_series_code": soil_series_code,
                            "soil_name": soil_name,
                            "area_sq_m": area_sq_m,
                        }
                        for (
                            soil_group_code,
                            soil_subgroup_code,
                            soil_series_code,
                            soil_name,
                        ), area_sq_m in areas_by_soil.items()
                    ],
                }
            )
        return results

    @staticmethod
    def _to_area_geometry(geometry: dict, transformer: Transformer):
        """入力座標のMultiPolygonを有効化し、等積投影へ変換する。"""
        result = shape(geometry)
        if not result.is_valid:
            result = make_valid(result)
        return transform(transformer.transform, result)

    @classmethod
    def _soil_to_area_geometry(cls, coordinates: list, transformer: Transformer):
        """既存の土壌図リング座標をPolygonまたはMultiPolygonとして等積投影へ変換する。"""
        polygons = []
        shell = None
        holes = []
        for ring_coordinates in coordinates:
            ring = LinearRing(ring_coordinates)
            if ring.is_ccw:
                holes.append(ring_coordinates)
                continue
            if shell:
                polygons.append(Polygon(shell, holes))
            shell = ring_coordinates
            holes = []
        if shell:
            polygons.append(Polygon(shell, holes))
        if not polygons:
            raise MunicipalitySoilAggregationError(
                "土壌図Polygonに外周リングがありません。"
            )
        result = polygons[0] if len(polygons) == 1 else MultiPolygon(polygons)
        if not result.is_valid:
            result = make_valid(result)
        return transform(transformer.transform, result)
