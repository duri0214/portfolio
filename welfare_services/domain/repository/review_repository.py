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
