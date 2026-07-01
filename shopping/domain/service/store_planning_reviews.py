from math import atan2, cos, radians, sin, sqrt

from gmarker.domain.service.google import GoogleMapsService
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from lib.geo.valueobject.coord import GoogleMapsCoord
from shopping.domain.valueobject.store_planning import StorePlanningTargetLocation
from shopping.domain.valueobject.store_planning_reviews import (
    StorePlanningReviewFetchResult,
    StorePlanningReview,
    StorePlanningReviewCell,
    StorePlanningReviewSummary,
)
from shopping.models import StorePlanningGoogleMapsReview, StorePlanningTargetStore


class StorePlanningReviewService:
    """保存済み Google Maps レビューを出店計画画面向けに集約する。"""

    RADIUS_METER = 500
    EARTH_RADIUS_METER = 6371000
    POSITIVE_KEYWORDS = [
        "おいしい",
        "美味",
        "便利",
        "良い",
        "いい",
        "最高",
        "親切",
        "清潔",
        "楽しい",
        "おすすめ",
        "落ち着",
    ]
    NEGATIVE_KEYWORDS = [
        "まずい",
        "高い",
        "遅い",
        "混雑",
        "うるさい",
        "汚",
        "悪い",
        "待",
        "不便",
        "狭い",
    ]
    CELL_LABELS = [
        ["北西", "北", "北東"],
        ["西", "中心", "東"],
        ["南西", "南", "南東"],
    ]
    API_FIELDS = [
        "places.id",
        "places.location",
        "places.displayName.text",
        "places.rating",
    ]
    DETAIL_FIELDS = [
        "id",
        "location",
        "displayName.text",
        "rating",
        "reviews",
    ]
    MAX_DETAIL_PLACES = 10

    @classmethod
    def fetch_reviews(
        cls, api_key: str, target_location: StorePlanningTargetLocation
    ) -> StorePlanningReviewFetchResult:
        """
        出店計画の対象店舗候補を検索し、取得できたレビューを保存する。
        """
        if target_location.latitude is None or target_location.longitude is None:
            return StorePlanningReviewFetchResult(place_count=0, review_count=0)

        target_store = StorePlanningTargetStore.objects.filter(
            slug=target_location.slug
        ).first()
        if target_store is None:
            return StorePlanningReviewFetchResult(place_count=0, review_count=0)
        existing_reviews = StorePlanningGoogleMapsReview.objects.filter(
            target_store_slug=target_store.slug
        )
        if existing_reviews.exists():
            return StorePlanningReviewFetchResult(
                place_count=existing_reviews.values("google_place_id")
                .distinct()
                .count(),
                review_count=existing_reviews.count(),
                skipped=True,
            )

        service = GoogleMapsService(api_key)
        center = GoogleMapsCoord(
            target_location.latitude,
            target_location.longitude,
        )
        exact_place_vos = service.text_search(
            query=f"{target_location.name} {target_location.address}",
            center=center,
            radius=cls.RADIUS_METER,
            fields=cls.API_FIELDS,
        )
        search_place_vos = cls._unique_place_vos(exact_place_vos)
        place_vo_list = cls._place_details_for_reviews(service, search_place_vos)
        review_count = 0
        for place_vo in place_vo_list:
            if place_vo.place is None or place_vo.location is None:
                continue
            for review in place_vo.reviews:
                author = review.author or review.google_maps_uri or "unknown"
                StorePlanningGoogleMapsReview.objects.update_or_create(
                    target_store=target_store,
                    target_store_slug=target_store.slug,
                    google_place_id=place_vo.place.place_id,
                    author=author,
                    defaults={
                        "place_name": place_vo.name or place_vo.place.name,
                        "latitude": place_vo.location.latitude,
                        "longitude": place_vo.location.longitude,
                        "rating": place_vo.rating,
                        "review_text": review.text or "",
                        "publish_time": cls._parse_publish_time(review.publish_time),
                        "google_maps_uri": review.google_maps_uri or "",
                        "fetched_at": timezone.now(),
                    },
                )
                review_count += 1
        return StorePlanningReviewFetchResult(
            place_count=len(place_vo_list),
            review_count=review_count,
        )

    @classmethod
    def _place_details_for_reviews(cls, service: GoogleMapsService, place_vos: list):
        detail_place_vos = []
        for place_vo in place_vos[: cls.MAX_DETAIL_PLACES]:
            detail_place_vo = service.place_details(
                place_id=place_vo.place.place_id,
                fields=cls.DETAIL_FIELDS,
            )
            if detail_place_vo is None:
                continue
            detail_place_vos.append(detail_place_vo)
        return detail_place_vos

    @staticmethod
    def _unique_place_vos(place_vos: list) -> list:
        unique_place_vos = []
        seen_place_ids = set()
        for place_vo in place_vos:
            if place_vo.place is None:
                continue
            place_id = place_vo.place.place_id
            if place_id in seen_place_ids:
                continue
            seen_place_ids.add(place_id)
            unique_place_vos.append(place_vo)
        return unique_place_vos

    @staticmethod
    def _parse_publish_time(value: str | None):
        if not value:
            return None
        parsed_value = parse_datetime(value)
        if parsed_value is None:
            return None
        if timezone.is_naive(parsed_value):
            return timezone.make_aware(parsed_value)
        return parsed_value

    @classmethod
    def build_summary(
        cls, target_location: StorePlanningTargetLocation
    ) -> StorePlanningReviewSummary:
        if target_location.latitude is None or target_location.longitude is None:
            return cls._empty_summary()

        cell_rows = cls._empty_cell_rows()
        latest_reviews = []
        place_ids = set()
        total_rating = 0.0
        rated_place_ids = set()
        positive_count = 0
        negative_count = 0

        target_store = StorePlanningTargetStore.objects.filter(
            slug=target_location.slug
        ).first()
        if target_store is None:
            return cls._empty_summary()

        for review in cls._review_queryset(target_store):
            distance_meter = cls._distance_meter(
                target_location.latitude,
                target_location.longitude,
                review.latitude,
                review.longitude,
            )
            if distance_meter > cls.RADIUS_METER:
                continue

            row, col = cls._grid_position(
                target_location.latitude,
                target_location.longitude,
                review.latitude,
                review.longitude,
            )
            place_ids.add(review.google_place_id)
            if (
                review.rating is not None
                and review.google_place_id not in rated_place_ids
            ):
                total_rating += review.rating
                rated_place_ids.add(review.google_place_id)

            planning_review = StorePlanningReview(
                place_name=review.place_name,
                author=review.author or "-",
                review_text=review.review_text or "",
                publish_time=review.publish_time,
                rating=review.rating,
                distance_meter=round(distance_meter),
            )
            cell_rows[row][col].append(planning_review)
            latest_reviews.append(planning_review)

            text = review.review_text or ""
            if cls._has_keyword(text, cls.POSITIVE_KEYWORDS):
                positive_count += 1
            if cls._has_keyword(text, cls.NEGATIVE_KEYWORDS):
                negative_count += 1

        latest_reviews.sort(
            key=lambda item: item.publish_time.timestamp() if item.publish_time else 0,
            reverse=True,
        )
        cells = cls._build_cells(cell_rows)
        average_rating = None
        if rated_place_ids:
            average_rating = round(total_rating / len(rated_place_ids), 1)
        return StorePlanningReviewSummary(
            radius_meter=cls.RADIUS_METER,
            total_place_count=len(place_ids),
            total_review_count=len(latest_reviews),
            average_rating=average_rating,
            positive_count=positive_count,
            negative_count=negative_count,
            cells=cells,
            latest_reviews=latest_reviews[:5],
        )

    @classmethod
    def _review_queryset(cls, target_store: StorePlanningTargetStore):
        return (
            StorePlanningGoogleMapsReview.objects.filter(
                target_store_slug=target_store.slug
            )
            .exclude(review_text__isnull=True)
            .exclude(review_text="")
            .order_by("-publish_time", "-id")
        )

    @classmethod
    def _empty_summary(cls) -> StorePlanningReviewSummary:
        return StorePlanningReviewSummary(
            radius_meter=cls.RADIUS_METER,
            total_place_count=0,
            total_review_count=0,
            average_rating=None,
            positive_count=0,
            negative_count=0,
            cells=cls._build_cells(cls._empty_cell_rows()),
            latest_reviews=[],
        )

    @classmethod
    def _empty_cell_rows(cls) -> list[list[list[StorePlanningReview]]]:
        return [[[] for _ in range(3)] for _ in range(3)]

    @classmethod
    def _build_cells(
        cls, cell_rows: list[list[list[StorePlanningReview]]]
    ) -> list[StorePlanningReviewCell]:
        cells = []
        for row in range(3):
            for col in range(3):
                reviews = cell_rows[row][col]
                place_ids = {review.place_name for review in reviews}
                ratings = [
                    review.rating for review in reviews if review.rating is not None
                ]
                average_rating = (
                    round(sum(ratings) / len(ratings), 1) if ratings else None
                )
                positive_count = sum(
                    cls._has_keyword(review.review_text, cls.POSITIVE_KEYWORDS)
                    for review in reviews
                )
                negative_count = sum(
                    cls._has_keyword(review.review_text, cls.NEGATIVE_KEYWORDS)
                    for review in reviews
                )
                score = cls._score(average_rating, positive_count, negative_count)
                cells.append(
                    StorePlanningReviewCell(
                        row=row,
                        col=col,
                        label=cls.CELL_LABELS[row][col],
                        place_count=len(place_ids),
                        review_count=len(reviews),
                        average_rating=average_rating,
                        positive_count=positive_count,
                        negative_count=negative_count,
                        score=score,
                        background_color=cls._background_color(score, len(reviews)),
                        text_color="#ffffff" if score >= 70 else "#212529",
                        reviews=reviews[:3],
                    )
                )
        return cells

    @classmethod
    def _score(
        cls, average_rating: float | None, positive_count: int, negative_count: int
    ) -> int:
        if average_rating is None:
            base_score = 50
        else:
            base_score = int(max(0, min(100, (average_rating - 1) / 4 * 100)))
        keyword_adjustment = (positive_count - negative_count) * 8
        return max(0, min(100, base_score + keyword_adjustment))

    @staticmethod
    def _background_color(score: int, review_count: int) -> str:
        if not review_count:
            return "#f8f9fa"
        if score >= 75:
            return "#b4472f"
        if score >= 60:
            return "#e3a642"
        if score >= 45:
            return "#f3df9b"
        return "#8fb9dd"

    @classmethod
    def _distance_meter(
        cls, origin_lat: float, origin_lng: float, lat: float, lng: float
    ) -> float:
        origin_lat_rad = radians(origin_lat)
        lat_rad = radians(lat)
        delta_lat = radians(lat - origin_lat)
        delta_lng = radians(lng - origin_lng)
        haversine = (
            sin(delta_lat / 2) ** 2
            + cos(origin_lat_rad) * cos(lat_rad) * sin(delta_lng / 2) ** 2
        )
        return cls.EARTH_RADIUS_METER * 2 * atan2(sqrt(haversine), sqrt(1 - haversine))

    @classmethod
    def _grid_position(
        cls, origin_lat: float, origin_lng: float, lat: float, lng: float
    ) -> tuple[int, int]:
        north_meter = (lat - origin_lat) * 111320
        east_meter = (lng - origin_lng) * 111320 * cos(radians(origin_lat))
        col = cls._axis_index(east_meter)
        row = 2 - cls._axis_index(north_meter)
        return row, col

    @classmethod
    def _axis_index(cls, meter: float) -> int:
        third = cls.RADIUS_METER / 3
        if meter < -third:
            return 0
        if meter > third:
            return 2
        return 1

    @staticmethod
    def _has_keyword(text: str, keywords: list[str]) -> bool:
        return any(keyword in text for keyword in keywords)
