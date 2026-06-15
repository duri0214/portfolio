from dataclasses import dataclass


@dataclass(frozen=True)
class CommercialAreaVO:
    """
    都道府県単位の農業商圏を表します。

    Attributes:
        prefecture_id: JMA都道府県マスタのID。
        prefecture_name: 都道府県名。
        land_count: 登録済み圃場数。
        company_count: 登録済み農業法人・企業数。
        main_crop_name: 最も多く台帳に登場する作物名。
        total_area: 圃場面積の合計。
        warning_city_count: 警報・注意報が登録されている市区町村数。
        risk_score: 商圏リスクスコア。警報と登録データ有無から算出する。
        map_row: 簡易日本地図グリッドの行番号。
        map_col: 簡易日本地図グリッドの列番号。
    """

    prefecture_id: int
    prefecture_name: str
    land_count: int
    company_count: int
    main_crop_name: str
    total_area: float
    warning_city_count: int
    risk_score: int
    map_row: int
    map_col: int

    @property
    def status_label(self) -> str:
        if self.warning_city_count:
            return "注意"
        if self.land_count:
            return "稼働"
        return "未登録"

    @property
    def status_class(self) -> str:
        if self.warning_city_count:
            return "area-risk"
        if self.land_count:
            return "area-active"
        return "area-empty"

    @property
    def map_position_class(self) -> str:
        return f"map-row-{self.map_row} map-col-{self.map_col}"


@dataclass(frozen=True)
class DispatchCandidateVO:
    """
    商圏から仮想市場への出荷候補を表します。

    Attributes:
        origin_name: 出荷元の都道府県商圏名。
        target_market_name: 仮想の出荷先市場名。
        main_crop_name: 出荷候補の主要作物名。
        logistics_status: 配車候補の状態。
        reason: 推奨理由。
        risk_score: 対象商圏のリスクスコア。
    """

    origin_name: str
    target_market_name: str
    main_crop_name: str
    logistics_status: str
    reason: str
    risk_score: int


@dataclass(frozen=True)
class NationalMarketVO:
    """
    47都道府県の商圏を束ねた全国市場ビューを表します。

    Attributes:
        areas: 都道府県単位の商圏一覧。
        dispatch_candidates: 出荷候補一覧。
    """

    areas: list[CommercialAreaVO]
    dispatch_candidates: list[DispatchCandidateVO]

    @property
    def area_count(self) -> int:
        return len(self.areas)

    @property
    def active_area_count(self) -> int:
        return sum(1 for area in self.areas if area.land_count)

    @property
    def risk_area_count(self) -> int:
        return sum(1 for area in self.areas if area.warning_city_count)

    @property
    def land_count(self) -> int:
        return sum(area.land_count for area in self.areas)

    @property
    def dispatch_candidate_count(self) -> int:
        return len(self.dispatch_candidates)

    @property
    def featured_areas(self) -> list[CommercialAreaVO]:
        return sorted(
            self.areas,
            key=lambda area: (area.risk_score, area.land_count, area.company_count),
            reverse=True,
        )[:8]
