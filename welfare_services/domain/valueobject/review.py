from dataclasses import dataclass


@dataclass(frozen=True)
class RatingDistributionVO:
    """評価分布のValueObject

    レビューの評価（1〜5）ごとの件数と構成比率を表します。

    使用例:
        # 5つ星が3件、全体の30%の場合
        RatingDistributionVO(rating=5, count=3, percentage=30.0)

        # 福祉事務所「XXX支援センター」の評価分布の例
        # 5つ星：6件（60.0%）
        # 4つ星：2件（20.0%）
        # 3つ星：1件（10.0%）
        # 2つ星：1件（10.0%）
        # 1つ星：0件（0.0%）
    """

    rating: int
    count: int
    percentage: float


@dataclass(frozen=True)
class ReviewStatsVO:
    """レビュー統計情報のValueObject

    施設のレビュー統計情報を表します。

    使用例:
        # 福祉事務所のレビュー統計情報
        ReviewStatsVO(
            average_rating=4.3, # 平均評価（小数点あり）
            average_rating_rounded=4, # 平均評価（四捨五入）
            total_reviews=10, # 総レビュー数
            rating_distribution=[ # 評価分布のリスト（5段階評価なので常に5要素、降順）
                RatingDistributionVO(rating=5, count=6, percentage=60.0),
                RatingDistributionVO(rating=4, count=2, percentage=20.0),
                RatingDistributionVO(rating=3, count=1, percentage=10.0),
                RatingDistributionVO(rating=2, count=1, percentage=10.0),
                RatingDistributionVO(rating=1, count=0, percentage=0.0)
            ])

        # リポジトリでの使用例:
        stats = ReviewRepository.get_review_stats(facility)
        print(f"平均評価: {stats.average_rating:.1f}")
        print(f"レビュー数: {stats.total_reviews}件")
    """

    average_rating: float
    average_rating_rounded: int
    total_reviews: int
    rating_distribution: list[RatingDistributionVO]
