from django.db.models import Count, FloatField, ExpressionWrapper, QuerySet
from django.db.models.functions import Cast

from welfare_services.domain.valueobject.review import (
    RatingDistributionVO,
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
