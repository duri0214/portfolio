from dataclasses import dataclass


@dataclass(frozen=True)
class RatingDistributionVO:
    """評価分布のValueObject

    レビューの評価（1〜5）ごとの件数と構成比率を表します。
    """
    rating: int
    count: int
    percentage: float


@dataclass(frozen=True)
class ReviewStatsVO:
    """レビュー統計情報のValueObject

    施設のレビュー統計情報を表します。
    """
    average_rating: float
    average_rating_rounded: int
    total_reviews: int
    rating_distribution: list[RatingDistributionVO]
