"""保存済みの全国土壌図から一点の分類を検索する。"""

from decimal import Decimal

from shapely import make_valid
from shapely.geometry import LinearRing, MultiPolygon, Point, Polygon

from soil_analysis.domain.repository.soil_map import SoilMapRepository
from soil_analysis.domain.service.soil_classification import SoilClassificationService
from soil_analysis.domain.valueobject.soil_classification import SOIL_INVENTORY_URL


class SoilPointSearchService:
    """外部サイトへ問い合わせず、保存済みPolygonだけで地点を検索する。"""

    MAP_ZOOM = 12

    @classmethod
    def search(cls, latitude: Decimal, longitude: Decimal) -> dict:
        """緯度・経度に対応する土壌分類、または検索できない理由を返す。"""
        latitude_value = float(latitude)
        longitude_value = float(longitude)
        dataset = SoilMapRepository.get_active_dataset()
        result = {
            "dataset": dataset,
            "latitude": latitude,
            "longitude": longitude,
            "inventory_map_url": (
                f"{SOIL_INVENTORY_URL}?lat={latitude}&lng={longitude}"
                f"&zoom={cls.MAP_ZOOM}"
            ),
        }
        if not dataset:
            return {**result, "status": "data_unavailable"}

        candidates = SoilMapRepository.get_point_candidates(
            dataset, latitude_value, longitude_value
        )
        point = Point(longitude_value, latitude_value)
        polygon = next(
            (
                candidate
                for candidate in candidates
                if cls._to_geometry(candidate.coordinates).covers(point)
            ),
            None,
        )
        if not polygon:
            extent = SoilMapRepository.get_dataset_extent(dataset)
            if cls._is_outside_extent(latitude_value, longitude_value, extent):
                return {**result, "status": "outside_coverage"}
            return {**result, "status": "not_classified"}

        if polygon.soil_group_code == "Z3":
            return {**result, "status": "non_soil", "polygon": polygon}

        group_code = polygon.soil_group_code
        return {
            **result,
            "status": "found",
            "polygon": polygon,
            "soil_name": SoilClassificationService.normalize_soil_name(
                polygon.soil_name
            ),
            "soil_group_name": SoilClassificationService.get_soil_group_name(
                group_code
            ),
            "soil_group_summary": SoilClassificationService.get_soil_group_summary(
                group_code
            ),
            "soil_group_url": SoilClassificationService.get_soil_group_url(group_code),
            "prefecture_id": int(polygon.prefecture_code),
        }

    @staticmethod
    def _is_outside_extent(
        latitude: float, longitude: float, extent: dict[str, float | None]
    ) -> bool:
        """地点が保存済み土壌図全体の外接矩形の外かを判定する。"""
        return (
            extent["min_lng"] is None
            or longitude < extent["min_lng"]
            or longitude > extent["max_lng"]
            or latitude < extent["min_lat"]
            or latitude > extent["max_lat"]
        )

    @staticmethod
    def _to_geometry(coordinates: list):
        """Shape由来のリング列を穴を含むShapely geometryへ変換する。"""
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
        geometry = polygons[0] if len(polygons) == 1 else MultiPolygon(polygons)
        return make_valid(geometry) if not geometry.is_valid else geometry
