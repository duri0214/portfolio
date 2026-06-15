from collections import Counter, defaultdict

from soil_analysis.domain.valueobject.market import (
    CommercialAreaVO,
    DispatchCandidateVO,
    NationalMarketVO,
)
from soil_analysis.models import JmaPrefecture, JmaWarning, Land, LandLedger


PREFECTURE_MAP_POSITIONS = {
    "北海道": (1, 7),
    "青森県": (2, 7),
    "岩手県": (3, 7),
    "宮城県": (4, 7),
    "秋田県": (3, 6),
    "山形県": (4, 6),
    "福島県": (5, 7),
    "茨城県": (6, 7),
    "栃木県": (6, 6),
    "群馬県": (6, 5),
    "埼玉県": (7, 6),
    "千葉県": (8, 7),
    "東京都": (8, 6),
    "神奈川県": (9, 6),
    "新潟県": (5, 5),
    "富山県": (6, 4),
    "石川県": (6, 3),
    "福井県": (7, 3),
    "山梨県": (8, 5),
    "長野県": (7, 5),
    "岐阜県": (8, 4),
    "静岡県": (9, 5),
    "愛知県": (9, 4),
    "三重県": (10, 5),
    "滋賀県": (8, 3),
    "京都府": (9, 3),
    "大阪府": (10, 3),
    "兵庫県": (9, 2),
    "奈良県": (11, 4),
    "和歌山県": (12, 4),
    "鳥取県": (8, 2),
    "島根県": (8, 1),
    "岡山県": (9, 2),
    "広島県": (9, 1),
    "山口県": (10, 1),
    "徳島県": (11, 2),
    "香川県": (10, 2),
    "愛媛県": (11, 1),
    "高知県": (12, 1),
    "福岡県": (11, 0),
    "佐賀県": (12, 0),
    "長崎県": (13, 0),
    "熊本県": (12, 1),
    "大分県": (12, 2),
    "宮崎県": (13, 2),
    "鹿児島県": (14, 2),
    "沖縄県": (15, 0),
}


class NationalMarketService:
    """既存の土壌分析データから全国商圏ダッシュボードを生成します。"""

    @classmethod
    def build(cls) -> NationalMarketVO:
        prefectures = list(JmaPrefecture.objects.all().order_by("code", "id"))
        land_stats = cls._build_land_stats()
        crop_stats = cls._build_crop_stats()
        warning_stats = cls._build_warning_stats()

        areas = [
            cls._build_area(prefecture, land_stats, crop_stats, warning_stats)
            for prefecture in prefectures
        ]
        dispatch_candidates = cls._build_dispatch_candidates(areas)
        return NationalMarketVO(areas=areas, dispatch_candidates=dispatch_candidates)

    @staticmethod
    def _build_land_stats() -> dict[int, dict]:
        stats = defaultdict(
            lambda: {"land_count": 0, "company_ids": set(), "total_area": 0.0}
        )
        lands = Land.objects.select_related(
            "company", "jma_city__jma_region__jma_prefecture"
        )
        for land in lands:
            prefecture_id = land.jma_city.jma_region.jma_prefecture_id
            stats[prefecture_id]["land_count"] += 1
            stats[prefecture_id]["company_ids"].add(land.company_id)
            stats[prefecture_id]["total_area"] += land.area or 0.0
        return stats

    @staticmethod
    def _build_crop_stats() -> dict[int, Counter]:
        stats = defaultdict(Counter)
        ledgers = LandLedger.objects.select_related(
            "crop", "land__jma_city__jma_region__jma_prefecture"
        )
        for ledger in ledgers:
            prefecture_id = ledger.land.jma_city.jma_region.jma_prefecture_id
            stats[prefecture_id][ledger.crop.name] += 1
        return stats

    @staticmethod
    def _build_warning_stats() -> Counter:
        warning_stats = Counter()
        warnings = JmaWarning.objects.select_related("jma_region__jma_prefecture")
        for warning in warnings:
            prefecture_id = warning.jma_region.jma_prefecture_id
            warning_stats[prefecture_id] += 1
        return warning_stats

    @classmethod
    def _build_area(
        cls,
        prefecture: JmaPrefecture,
        land_stats: dict[int, dict],
        crop_stats: dict[int, Counter],
        warning_stats: Counter,
    ) -> CommercialAreaVO:
        stats = land_stats[prefecture.id]
        warning_city_count = warning_stats[prefecture.id]
        land_count = stats["land_count"]
        risk_score = cls._calculate_risk_score(land_count, warning_city_count)
        map_row, map_col = PREFECTURE_MAP_POSITIONS.get(prefecture.name, (16, 0))
        main_crop_name = cls._get_main_crop_name(crop_stats[prefecture.id])

        return CommercialAreaVO(
            prefecture_id=prefecture.id,
            prefecture_name=prefecture.name,
            land_count=land_count,
            company_count=len(stats["company_ids"]),
            main_crop_name=main_crop_name,
            total_area=round(stats["total_area"], 2),
            warning_city_count=warning_city_count,
            risk_score=risk_score,
            map_row=map_row,
            map_col=map_col,
        )

    @staticmethod
    def _calculate_risk_score(land_count: int, warning_city_count: int) -> int:
        if warning_city_count:
            return min(100, 70 + warning_city_count * 5)
        if land_count:
            return 30
        return 0

    @staticmethod
    def _get_main_crop_name(crop_counter: Counter) -> str:
        if not crop_counter:
            return "未設定"
        return crop_counter.most_common(1)[0][0]

    @staticmethod
    def _build_dispatch_candidates(
        areas: list[CommercialAreaVO],
    ) -> list[DispatchCandidateVO]:
        active_areas = [area for area in areas if area.land_count]
        sorted_areas = sorted(
            active_areas,
            key=lambda area: (area.warning_city_count == 0, area.land_count),
            reverse=True,
        )

        candidates = []
        for index, area in enumerate(sorted_areas[:5]):
            market_name = "首都圏市場" if index % 2 == 0 else "関西市場"
            logistics_status = (
                "配車候補あり" if not area.warning_city_count else "天候確認中"
            )
            if area.warning_city_count:
                reason = f"{area.prefecture_name}は警報・注意報があるため、代替ルート確認を優先します。"
            else:
                reason = f"{area.prefecture_name}は圃場登録があり、{area.main_crop_name}の出荷候補として監視します。"

            candidates.append(
                DispatchCandidateVO(
                    origin_name=area.prefecture_name,
                    target_market_name=market_name,
                    main_crop_name=area.main_crop_name,
                    logistics_status=logistics_status,
                    reason=reason,
                    risk_score=area.risk_score,
                )
            )
        return candidates
