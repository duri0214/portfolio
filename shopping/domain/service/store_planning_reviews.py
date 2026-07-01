from math import atan2, cos, radians, sin, sqrt

from gmarker.domain.repository.google import PlaceReviewRepository
from gmarker.domain.service.google import GoogleMapsService
from gmarker.models import PlaceReview
from lib.geo.valueobject.coord import GoogleMapsCoord
from shopping.domain.valueobject.store_planning import StorePlanningTargetLocation
from shopping.domain.valueobject.store_planning_reviews import (
    StorePlanningReviewFetchResult,
    StorePlanningReview,
    StorePlanningReviewCell,
    StorePlanningReviewSummary,
)


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
    SEARCH_TYPES = ["restaurant", "cafe", "bar", "bakery"]
    API_FIELDS = [
        "places.id",
        "places.location",
        "places.displayName.text",
        "places.rating",
        "places.reviews",
    ]

    @classmethod
    def fetch_reviews(
        cls, api_key: str, target_location: StorePlanningTargetLocation
    ) -> StorePlanningReviewFetchResult:
        """
        出店計画の対象地点を中心に Places API からレビューを取得して保存する。

        gmarker の GoogleMapsService で Nearby Search を実行し、取得済みの
        PlaceVO に含まれるレビューを gmarker の PlaceReview として保存する。
        NearbyPlace のカテゴリ検索結果は更新せず、shopping のレビュー分析に
        必要な Place / PlaceReview だけを再利用する。
        """
        if target_location.latitude is None or target_location.longitude is None:
            return StorePlanningReviewFetchResult(place_count=0, review_count=0)

        service = GoogleMapsService(api_key)
        place_vo_list = service.nearby_search(
            center=GoogleMapsCoord(
                target_location.latitude,
                target_location.longitude,
            ),
            search_types=cls.SEARCH_TYPES,
            radius=cls.RADIUS_METER,
            fields=cls.API_FIELDS,
        )
        review_count = 0
        for place_vo in place_vo_list:
            place_reviews = [
                PlaceReview(
                    review_text=review.text,
                    author=review.author,
                    publish_time=review.publish_time,
                    google_maps_uri=review.google_maps_uri,
                    place=place_vo.place,
                )
                for review in place_vo.reviews
            ]
            review_count += len(place_reviews)
            PlaceReviewRepository.bulk_create(place_reviews)
        return StorePlanningReviewFetchResult(
            place_count=len(place_vo_list),
            review_count=review_count,
        )

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

        for review in cls._review_queryset():
            place_coord = cls._parse_location(review.place.location)
            if place_coord is None:
                continue

            distance_meter = cls._distance_meter(
                target_location.latitude,
                target_location.longitude,
                place_coord[0],
                place_coord[1],
            )
            if distance_meter > cls.RADIUS_METER:
                continue

            row, col = cls._grid_position(
                target_location.latitude,
                target_location.longitude,
                place_coord[0],
                place_coord[1],
            )
            place_ids.add(review.place_id)
            if (
                review.place.rating is not None
                and review.place_id not in rated_place_ids
            ):
                total_rating += review.place.rating
                rated_place_ids.add(review.place_id)

            planning_review = StorePlanningReview(
                place_name=review.place.name,
                author=review.author or "-",
                review_text=review.review_text or "",
                publish_time=review.publish_time,
                rating=review.place.rating,
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
    def _review_queryset(cls):
        return (
            PlaceReview.objects.select_related("place")
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

    @staticmethod
    def _parse_location(location: str | None) -> tuple[float, float] | None:
        if not location:
            return None
        parts = [part.strip() for part in location.split(",")]
        if len(parts) != 2:
            return None
        try:
            return float(parts[0]), float(parts[1])
        except ValueError:
            return None

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
