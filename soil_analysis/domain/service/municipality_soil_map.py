"""市区町村別土壌面積の画面表示用データを組み立てるサービス。"""

from collections import defaultdict

from soil_analysis.domain.repository.municipality_soil import (
    MunicipalitySoilRepository,
)


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
            "boundary_source_url": cls.SOURCE_URL,
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
                "boundary_source_url": cls.SOURCE_URL,
            }
        rows = list(MunicipalitySoilRepository.get_soil_area_rows(aggregation))
        return {
            "soil_dataset": soil_dataset,
            "boundary_dataset": boundary_dataset,
            "municipality": municipality,
            "prefecture_id": int(municipality.prefecture_code),
            "aggregation": aggregation,
            "soil_group_rows": cls._summary_rows(rows, ("soil_group_code",)),
            "soil_subgroup_rows": cls._summary_rows(
                rows, ("soil_group_code", "soil_subgroup_code")
            ),
            "soil_series_rows": cls._summary_rows(
                rows,
                ("soil_group_code", "soil_subgroup_code", "soil_series_code"),
            ),
            "soil_name_rows": cls._summary_rows(
                rows,
                (
                    "soil_group_code",
                    "soil_subgroup_code",
                    "soil_series_code",
                    "soil_name",
                ),
            ),
            "boundary_source_url": cls.SOURCE_URL,
        }

    @staticmethod
    def _summary_rows(rows, fields: tuple[str, ...]) -> list[dict]:
        """分類列ごとに面積と、分類済み面積に対する構成比を返す。"""
        area_by_key = defaultdict(float)
        for row in rows:
            area_by_key[tuple(getattr(row, field) for field in fields)] += row.area_sq_m
        total = sum(area_by_key.values())
        return [
            {
                **dict(zip(fields, key)),
                "area_sq_m": area,
                "ratio": area / total * 100 if total else 0,
            }
            for key, area in sorted(
                area_by_key.items(), key=lambda item: (-item[1], item[0])
            )
        ]
