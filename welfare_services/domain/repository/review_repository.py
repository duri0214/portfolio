from django.db.models import Count, FloatField, ExpressionWrapper, QuerySet
from django.db.models.functions import Cast

from welfare_services.domain.valueobject.review import (
    RatingDistributionVO,
    ReviewStatsVO,
)
from welfare_services.models import FacilityReview, Facility


class ReviewRepository:
    @staticmethod
    def get_facility_reviews(facility: Facility, is_approved: bool = True):
        """施設のレビューを取得する

        Args:
            facility: レビューを取得する施設
            is_approved: 承認済みレビューのみを取得するかどうか

        Returns:
            施設のレビューのクエリセット（最新順にソート）
        """
        return FacilityReview.objects.filter(
            facility=facility, is_approved=is_approved
        ).order_by("-created_at")

    @staticmethod
    def get_review_stats(facility: Facility, is_approved: bool = True):
        """施設のレビュー統計を取得する

        Args:
            facility: 統計を取得する施設
            is_approved: 承認済みレビューのみを対象とするかどうか

        Returns:
            ReviewStatsVO: レビュー統計情報を表すValueObject
                - average_rating: 平均評価（加重平均）
                - average_rating_rounded: 平均評価（整数に丸めた値）
                - total_reviews: レビュー総数
                - rating_distribution: 評価分布のリスト

        Notes:
            average_ratingは加重平均で計算されます（評価分布から直接計算できる）：
            加重平均 = (評価値1×件数1 + 評価値2×件数2 + ... + 評価値n×件数n) ÷ 総件数

            例えば「5つ星が3件、4つ星が2件、3つ星が1件」の場合：
            (5×3 + 4×2 + 3×1) ÷ (3+2+1) = 4.33...
        """
        # レビューを取得
        reviews = ReviewRepository.get_facility_reviews(facility, is_approved)

        # 総レビュー数を取得
        total_reviews = reviews.count()

        # 評価分布データをSQLで一括生成
        rating_distribution = ReviewRepository.get_rating_distribution(reviews)

        # レビューがない場合は0で返却
        if total_reviews == 0:
            return ReviewStatsVO(
                average_rating=0,
                average_rating_rounded=0,
                total_reviews=0,
                rating_distribution=rating_distribution,
            )

        # 評価分布から加重平均を計算
        weighted_sum = sum(dist.rating * dist.count for dist in rating_distribution)
        average_rating = weighted_sum / total_reviews
        average_rating_rounded = int(average_rating)

        # ValueObjectを生成して返却
        return ReviewStatsVO(
            average_rating=average_rating,
            average_rating_rounded=average_rating_rounded,
            total_reviews=total_reviews,
            rating_distribution=rating_distribution,
        )

    @staticmethod
    def get_rating_distribution(reviews: QuerySet) -> list[RatingDistributionVO]:
        """レビューの評価分布を取得する

        評価（1〜5）ごとの件数と構成比率をSQLで集計します。
        0件の評価（例：評価4のレビューが0件）も含めて結果を返します。

        Args:
            reviews: 評価分布を計算するレビューのクエリセット

        Returns:
            List[RatingDistributionVO]: 評価分布のValueObjectリスト（降順で5→1）
                各要素は以下の属性を持ちます：
                - rating: 評価値（1〜5）
                - count: レビュー数
                - percentage: パーセンテージ
        """
        # 総レビュー数を取得
        total_reviews = reviews.count()

        if total_reviews == 0:
            return [
                RatingDistributionVO(rating=r, count=0, percentage=0.0)
                for r in range(5, 0, -1)
            ]

        rating_data = list(
            reviews.values("rating").annotate(
                count=Count("rating"),
                percentage=ExpressionWrapper(
                    100.0 * Cast(Count("rating"), FloatField()) / total_reviews,
                    output_field=FloatField(),
                ),
            )
        )

        # 評価値をキーとする辞書を作成（高速検索のため）
        rating_dict = {item["rating"]: item for item in rating_data}

        # 評価1〜5の全てを網羅したリストを作成（降順）
        rating_distribution = []
        for rating in range(5, 0, -1):
            if rating in rating_dict:
                item = rating_dict[rating]
                rating_distribution.append(
                    RatingDistributionVO(
                        rating=item["rating"],
                        count=item["count"],
                        percentage=item["percentage"],
                    )
                )
            else:
                # 0件の評価を追加
                rating_distribution.append(
                    RatingDistributionVO(rating=rating, count=0, percentage=0.0)
                )

        return rating_distribution
