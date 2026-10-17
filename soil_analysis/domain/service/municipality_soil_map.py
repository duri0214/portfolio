"""市区町村別土壌面積の画面表示用データを組み立てるサービス。"""

from collections import defaultdict

from shapely.geometry import shape

from soil_analysis.domain.repository.municipality_soil import (
    MunicipalitySoilRepository,
)
from soil_analysis.domain.service.soil_classification import SoilClassificationService
from soil_analysis.domain.valueobject.soil_classification import SOIL_INVENTORY_URL


class MunicipalitySoilMapService:
    """市区町村一覧と土壌分類別内訳を表示用に変換する。"""

    SOURCE_URL = "https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2024.html"

    @classmethod
    def build_prefecture_context(cls, prefecture_code: str) -> dict:
        """都道府県ページ用の市区町村一覧と入力版情報を返す。"""
        soil_dataset = MunicipalitySoilRepository.get_active_soil_dataset()
        boundary_dataset = MunicipalitySoilRepository.get_active_boundary_dataset()
        municipalities = []
        if boundary_dataset:
            municipalities = list(
                MunicipalitySoilRepository.get_municipalities_for_prefecture(
                    boundary_dataset, prefecture_code
                )
            )
        aggregation_by_code = {}
        if soil_dataset and boundary_dataset:
            aggregation_by_code = {
                aggregation.municipality.municipality_code: aggregation
                for aggregation in MunicipalitySoilRepository.get_prefecture_aggregations(
                    soil_dataset, boundary_dataset, prefecture_code
                )
            }
        return {
            "soil_dataset": soil_dataset,
            "boundary_dataset": boundary_dataset,
            "municipalities": [
                {
                    "boundary": municipality,
                    "aggregation": aggregation_by_code.get(
                        municipality.municipality_code
                    ),
                }
                for municipality in municipalities
            ],
            "boundary_source_url": cls._boundary_source_url(boundary_dataset),
        }

    @classmethod
    def build_municipality_context(cls, municipality_code: str) -> dict | None:
        """市区町村詳細ページ用の面積と分類別構成比を返す。"""
        soil_dataset = MunicipalitySoilRepository.get_active_soil_dataset()
        boundary_dataset = MunicipalitySoilRepository.get_active_boundary_dataset()
        if not soil_dataset or not boundary_dataset:
            return None
        municipality = MunicipalitySoilRepository.get_municipality(
            boundary_dataset, municipality_code
        )
        if not municipality:
            return None
        aggregation = MunicipalitySoilRepository.get_aggregation(
            soil_dataset, boundary_dataset, municipality
        )
        if not aggregation:
            return {
                "soil_dataset": soil_dataset,
                "boundary_dataset": boundary_dataset,
                "municipality": municipality,
                "prefecture_id": int(municipality.prefecture_code),
                "aggregation": None,
                "boundary_source_url": cls._boundary_source_url(boundary_dataset),
            }
        rows = list(MunicipalitySoilRepository.get_soil_area_rows(aggregation))
        soil_group_rows = cls._summary_rows(rows, ("soil_group_code",))
        cls._add_national_group_comparison(
            soil_group_rows,
            soil_dataset,
            boundary_dataset,
        )
        return {
            "soil_dataset": soil_dataset,
            "boundary_dataset": boundary_dataset,
            "municipality": municipality,
            "prefecture_id": int(municipality.prefecture_code),
            "aggregation": aggregation,
            "soil_group_rows": soil_group_rows,
            "soil_subgroup_rows": cls._summary_rows(
                rows, ("soil_group_code", "soil_subgroup_code")
            ),
            "soil_series_rows": cls._summary_rows(
                rows,
                ("soil_group_code", "soil_subgroup_code", "soil_series_code"),
            ),
            "soil_name_rows": cls._summary_rows(rows, ("soil_name",)),
            "boundary_source_url": cls._boundary_source_url(boundary_dataset),
            "soil_inventory_url": SOIL_INVENTORY_URL,
            "soil_inventory_map_url": cls._soil_inventory_map_url(municipality),
        }

    @classmethod
    def _boundary_source_url(cls, boundary_dataset) -> str:
        """登録した行政区域データと同じ基準年の配布ページを返す。"""
        if boundary_dataset and boundary_dataset.source_date:
            return (
                "https://nlftp.mlit.go.jp/ksj/gml/datalist/"
                f"KsjTmplt-N03-{boundary_dataset.source_date.year}.html"
            )
        return cls.SOURCE_URL

    @staticmethod
    def _soil_inventory_map_url(municipality) -> str:
        """市区町村境界内の代表地点を指定する農研機構地図URLを返す。"""
        geometry = shape(
            {"type": "MultiPolygon", "coordinates": municipality.coordinates}
        )
        point = geometry.representative_point()
        return f"{SOIL_INVENTORY_URL}?lat={point.y:.6f}&lng={point.x:.6f}&zoom=12"

    @staticmethod
    def _summary_rows(rows, fields: tuple[str, ...]) -> list[dict]:
        """分類列ごとに面積と、分類済み面積に対する構成比を返す。"""
        area_by_key = defaultdict(float)
        for row in rows:
            area_by_key[tuple(getattr(row, field) for field in fields)] += row.area_sq_m
        total = sum(area_by_key.values())
        summary_rows = []
        for key, area in sorted(
            area_by_key.items(), key=lambda item: (-item[1], item[0])
        ):
            row = {
                **dict(zip(fields, key)),
                "area_sq_m": area,
                "ratio": area / total * 100 if total else 0,
            }
            if "soil_name" in row:
                row["soil_name_display"] = (
                    SoilClassificationService.normalize_soil_name(row["soil_name"])
                )
            summary_rows.append(row)
        return summary_rows

    @staticmethod
    def _add_national_group_comparison(
        soil_group_rows: list[dict], soil_dataset, boundary_dataset
    ) -> None:
        """市区町村の土壌群に、同じ集計版における全国順位と面積比を加える。"""
        national_rows = list(
            MunicipalitySoilRepository.get_national_soil_group_areas(
                soil_dataset, boundary_dataset
            )
        )
        national_total = sum(row["area_sq_m"] for row in national_rows)
        national_by_code = {
            row["soil_group_code"]: {
                "national_rank": rank,
                "national_ratio": (
                    row["area_sq_m"] / national_total * 100 if national_total else 0
                ),
                "group_count": len(national_rows),
            }
            for rank, row in enumerate(national_rows, start=1)
        }
        for row in soil_group_rows:
            code = row["soil_group_code"]
            row["soil_group_name"] = SoilClassificationService.get_soil_group_name(code)
            row["soil_group_summary"] = (
                SoilClassificationService.get_soil_group_summary(code)
            )
            row["soil_group_url"] = SoilClassificationService.get_soil_group_url(code)
            row.update(national_by_code.get(code, {}))
