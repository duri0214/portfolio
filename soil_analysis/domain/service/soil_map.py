"""土壌図の有効版を都道府県地図に表示するサービス。"""

from collections import defaultdict

from soil_analysis.domain.repository.soil_map import SoilMapRepository
from soil_analysis.domain.service.prefecture_commercial_area import (
    JAPAN_MAP_PREFECTURES,
)


class SoilMapService:
    """有効な土壌図を、既存の47都道府県マップ用データへ集計する。"""

    PALETTES = (
        {"color": "#dbeafe", "hoverColor": "#bfdbfe"},
        {"color": "#dcfce7", "hoverColor": "#bbf7d0"},
        {"color": "#fef3c7", "hoverColor": "#fde68a"},
        {"color": "#fae8ff", "hoverColor": "#f5d0fe"},
        {"color": "#ffedd5", "hoverColor": "#fed7aa"},
    )
    EMPTY_PALETTE = {"color": "#f1f5f9", "hoverColor": "#e2e8f0"}

    @classmethod
    def build_payload(cls) -> dict:
        """地図データと、画面に表示する出典メタデータを返す。"""
        dataset = SoilMapRepository.get_active_dataset()
        areas = {
            f"{code:02d}": {
                "code": code,
                "name": name,
                "polygonCount": 0,
                "soilName": None,
                "soilGroupCode": None,
                "color": cls.EMPTY_PALETTE["color"],
                "hoverColor": cls.EMPTY_PALETTE["hoverColor"],
            }
            for code, name in JAPAN_MAP_PREFECTURES
        }
        if not dataset:
            return {"areas": list(areas.values()), "dataset": None}

        grouped = defaultdict(list)
        summaries = SoilMapRepository.get_prefecture_soil_summaries(dataset)
        for summary in summaries:
            grouped[summary["prefecture_code"]].append(summary)
        for prefecture_code, summaries_for_prefecture in grouped.items():
            area = areas.get(prefecture_code)
            if not area:
                continue
            main = summaries_for_prefecture[0]
            palette = cls.PALETTES[
                sum(map(ord, main["soil_group_code"])) % len(cls.PALETTES)
            ]
            area.update(
                {
                    "polygonCount": sum(
                        item["polygon_count"] for item in summaries_for_prefecture
                    ),
                    "soilName": main["soil_name"],
                    "soilGroupCode": main["soil_group_code"],
                    "color": palette["color"],
                    "hoverColor": palette["hoverColor"],
                }
            )
        return {
            "areas": list(areas.values()),
            "dataset": {
                "sourceFileName": dataset.source_file_name,
                "featureCount": dataset.feature_count,
                "importedAt": dataset.imported_at.isoformat(),
                "sourceUrl": "https://soil-inventory.rad.naro.go.jp/download20.html",
            },
        }
