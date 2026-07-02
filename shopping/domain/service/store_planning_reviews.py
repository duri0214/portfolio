from math import atan2, cos, radians, sin, sqrt
from urllib.parse import urlencode

from django.utils import timezone
from django.utils.dateparse import parse_datetime
from lib.geo.valueobject.coord import GoogleMapsCoord
from shopping.domain.dataprovider.google_maps_review_analysis import (
    GoogleMapsReviewAnalysisClient,
)
from shopping.domain.dataprovider.google_maps_reviews import GoogleMapsReviewClient
from shopping.domain.valueobject.store_planning import StorePlanningTargetLocation
from shopping.domain.valueobject.store_planning_reviews import (
    StorePlanningPlaceInsight,
    StorePlanningReviewAnalysisFetchResult,
    StorePlanningReviewFetchResult,
    StorePlanningReview,
    StorePlanningReviewCell,
    StorePlanningReviewSummary,
)
from shopping.models import (
    StorePlanningGoogleMapsReview,
    StorePlanningGoogleMapsReviewAnalysis,
    StorePlanningGoogleMapsPlaceSummary,
    StorePlanningTargetStore,
)


class StorePlanningReviewService:
    """
    保存済み Google Maps レビューを出店計画画面向けに集約する。

    ポジティブ・ネガティブ件数は固定キーワードの含有数を数える軽量な目安であり、
    レビュー本文の意味分析や要約は行わない。本格的な評判分析は #820 で扱う。
    """

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
    MAX_ANALYSIS_REVIEWS = 10
    MAX_PLACE_INSIGHTS = 10
    GCP_CREDENTIALS_URL = "https://console.cloud.google.com/apis/credentials"
    TARGET_STORE_SCOPE = StorePlanningGoogleMapsReview.ReviewScope.TARGET_STORE
    NEARBY_SAME_BUSINESS_SCOPE = (
        StorePlanningGoogleMapsReview.ReviewScope.NEARBY_SAME_BUSINESS
    )

    @classmethod
    def fetch_reviews(
        cls,
        api_key: str,
        target_location: StorePlanningTargetLocation,
        force_refetch: bool = False,
    ) -> StorePlanningReviewFetchResult:
        """
        出店計画の対象店舗候補を検索し、取得できたレビューを保存する。
        """
        query = f"{target_location.name} {target_location.address}"
        return cls._fetch_reviews(
            api_key=api_key,
            target_location=target_location,
            query=query,
            review_scope=cls.TARGET_STORE_SCOPE,
            exclude_target_store=False,
            force_refetch=force_refetch,
        )

    @classmethod
    def fetch_nearby_same_business_reviews(
        cls,
        api_key: str,
        target_location: StorePlanningTargetLocation,
        force_refetch: bool = False,
    ) -> StorePlanningReviewFetchResult:
        """
        対象店舗候補と同じ業態の周辺店舗を検索し、レビューを保存する。
        """
        if not target_location.business_search_query:
            return StorePlanningReviewFetchResult(place_count=0, review_count=0)
        query = (
            f"{target_location.business_search_query} "
            f"{target_location.population_area}"
        )
        return cls._fetch_reviews(
            api_key=api_key,
            target_location=target_location,
            query=query,
            review_scope=cls.NEARBY_SAME_BUSINESS_SCOPE,
            exclude_target_store=True,
            force_refetch=force_refetch,
        )

    @classmethod
    def _fetch_reviews(
        cls,
        api_key: str,
        target_location: StorePlanningTargetLocation,
        query: str,
        review_scope: str,
        exclude_target_store: bool,
        force_refetch: bool,
    ) -> StorePlanningReviewFetchResult:
        if target_location.latitude is None or target_location.longitude is None:
            return StorePlanningReviewFetchResult(place_count=0, review_count=0)

        target_store = StorePlanningTargetStore.objects.filter(
            slug=target_location.slug
        ).first()
        if target_store is None:
            return StorePlanningReviewFetchResult(place_count=0, review_count=0)
        existing_reviews = cls._review_queryset(target_store, review_scope)
        if existing_reviews.exists() and not force_refetch:
            return StorePlanningReviewFetchResult(
                place_count=existing_reviews.values("google_place_id")
                .distinct()
                .count(),
                review_count=existing_reviews.count(),
                skipped=True,
            )

        client = GoogleMapsReviewClient(api_key)
        center = GoogleMapsCoord(
            target_location.latitude,
            target_location.longitude,
        )
        exact_place_vos = client.text_search(
            query=query,
            center=center,
            radius=cls.RADIUS_METER,
            fields=cls.API_FIELDS,
        )
        if client.last_error_status_code:
            return StorePlanningReviewFetchResult(
                place_count=0,
                review_count=0,
                error_message=cls._fetch_error_message(
                    client.last_error_status_code,
                    client.last_error_message,
                    client.last_error_operation,
                ),
                error_url=cls._fetch_error_url(client.last_error_status_code),
                error_url_label="GCP 認証情報を開く",
            )
        search_place_vos = cls._unique_place_vos(exact_place_vos)
        if exclude_target_store:
            search_place_vos = cls._exclude_target_store_place(
                search_place_vos, target_location
            )
        place_vo_list = cls._place_details_for_reviews(client, search_place_vos)
        if client.last_error_status_code:
            return StorePlanningReviewFetchResult(
                place_count=len(search_place_vos),
                review_count=0,
                error_message=cls._fetch_error_message(
                    client.last_error_status_code,
                    client.last_error_message,
                    client.last_error_operation,
                ),
                error_url=cls._fetch_error_url(client.last_error_status_code),
                error_url_label="GCP 認証情報を開く",
            )
        review_count = 0
        for place_vo in place_vo_list:
            if place_vo.location is None:
                continue
            for review in place_vo.reviews:
                if not review.text:
                    continue
                author = review.author or review.google_maps_uri or "unknown"
                StorePlanningGoogleMapsReview.objects.update_or_create(
                    target_store=target_store,
                    target_store_slug=target_store.slug,
                    review_scope=review_scope,
                    google_place_id=place_vo.place_id,
                    author=author,
                    defaults={
                        "place_name": place_vo.name or place_vo.place_id,
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
    def analyze_nearby_same_business_reviews(
        cls, api_key: str, target_location: StorePlanningTargetLocation
    ) -> StorePlanningReviewAnalysisFetchResult:
        """
        周辺同業レビューを店舗単位でLLM分析し、サマリーテーブルへ保存する。
        """
        return cls.analyze_place_summaries(
            api_key=api_key,
            target_location=target_location,
            review_scope=cls.NEARBY_SAME_BUSINESS_SCOPE,
        )

    @classmethod
    def analyze_all_reviews(
        cls, api_key: str, target_location: StorePlanningTargetLocation
    ) -> StorePlanningReviewAnalysisFetchResult:
        """
        対象店舗と周辺同業レビューを同じ分析軸でLLM分析する。
        """
        target_result = cls.analyze_place_summaries(
            api_key=api_key,
            target_location=target_location,
            review_scope=cls.TARGET_STORE_SCOPE,
        )
        nearby_result = cls.analyze_place_summaries(
            api_key=api_key,
            target_location=target_location,
            review_scope=cls.NEARBY_SAME_BUSINESS_SCOPE,
        )
        error_message = target_result.error_message or nearby_result.error_message
        return StorePlanningReviewAnalysisFetchResult(
            analyzed_count=target_result.analyzed_count + nearby_result.analyzed_count,
            positive_count=target_result.positive_count + nearby_result.positive_count,
            negative_count=target_result.negative_count + nearby_result.negative_count,
            skipped=target_result.skipped and nearby_result.skipped,
            error_message=error_message,
        )

    @classmethod
    def analyze_place_summaries(
        cls,
        api_key: str,
        target_location: StorePlanningTargetLocation,
        review_scope: str,
    ) -> StorePlanningReviewAnalysisFetchResult:
        """
        指定されたレビュー種別を店舗単位に集約し、サマリー後レコードを保存する。
        """
        target_store = StorePlanningTargetStore.objects.filter(
            slug=target_location.slug
        ).first()
        if target_store is None:
            return StorePlanningReviewAnalysisFetchResult(
                analyzed_count=0, positive_count=0, negative_count=0, skipped=True
            )

        grouped_reviews = cls._grouped_reviews_for_summary(target_store, review_scope)
        if not grouped_reviews:
            return StorePlanningReviewAnalysisFetchResult(
                analyzed_count=0, positive_count=0, negative_count=0, skipped=True
            )

        summary_map = {
            summary.google_place_id: summary
            for summary in StorePlanningGoogleMapsPlaceSummary.objects.filter(
                target_store_slug=target_store.slug,
                review_scope=review_scope,
            )
        }
        target_groups = [
            group
            for group in grouped_reviews
            if group["google_place_id"] not in summary_map
            or summary_map[group["google_place_id"]].review_count
            != group["review_count"]
        ]
        if not target_groups:
            return StorePlanningReviewAnalysisFetchResult(
                analyzed_count=0, positive_count=0, negative_count=0, skipped=True
            )

        client = GoogleMapsReviewAnalysisClient(api_key)
        summary_results = client.analyze_place_summaries(target_groups)
        if not summary_results:
            return StorePlanningReviewAnalysisFetchResult(
                analyzed_count=0,
                positive_count=0,
                negative_count=0,
                error_message="レビュー分析の結果を読み取れませんでした。",
            )

        group_map = {group["google_place_id"]: group for group in target_groups}
        saved_count = 0
        positive_count = 0
        negative_count = 0
        for summary_result in summary_results:
            group = group_map.get(summary_result.google_place_id)
            if group is None:
                continue
            positive_count += summary_result.positive_count
            negative_count += summary_result.negative_count
            StorePlanningGoogleMapsPlaceSummary.objects.update_or_create(
                target_store=target_store,
                target_store_slug=target_store.slug,
                review_scope=review_scope,
                google_place_id=summary_result.google_place_id,
                defaults={
                    "place_name": group["place_name"],
                    "rating": group["rating"],
                    "review_count": group["review_count"],
                    "positive_count": summary_result.positive_count,
                    "negative_count": summary_result.negative_count,
                    "sentiment_score": summary_result.sentiment_score,
                    "one_line_summary": summary_result.one_line_summary,
                    "issue": summary_result.issue,
                    "next_action": summary_result.next_action,
                    "location_insight": summary_result.location_insight,
                    "model_name": client.model_name,
                    "prompt_version": client.PROMPT_VERSION,
                    "raw_response": summary_result.raw_response,
                    "analyzed_at": timezone.now(),
                },
            )
            saved_count += 1

        return StorePlanningReviewAnalysisFetchResult(
            analyzed_count=saved_count,
            positive_count=positive_count,
            negative_count=negative_count,
        )

    @classmethod
    def analyze_reviews(
        cls,
        api_key: str,
        target_location: StorePlanningTargetLocation,
        review_scope: str,
    ) -> StorePlanningReviewAnalysisFetchResult:
        """
        指定されたレビュー種別をLLMで分析し、レビュー子テーブルへ保存する。
        """
        target_store = StorePlanningTargetStore.objects.filter(
            slug=target_location.slug
        ).first()
        if target_store is None:
            return StorePlanningReviewAnalysisFetchResult(
                analyzed_count=0, positive_count=0, negative_count=0, skipped=True
            )

        reviews = list(
            cls._review_queryset(target_store, review_scope)
            .filter(analysis__isnull=True)
            .order_by("-rating", "-publish_time", "-id")[: cls.MAX_ANALYSIS_REVIEWS]
        )
        if not reviews:
            return StorePlanningReviewAnalysisFetchResult(
                analyzed_count=0, positive_count=0, negative_count=0, skipped=True
            )

        client = GoogleMapsReviewAnalysisClient(api_key)
        analysis_results = client.analyze_reviews(reviews)
        if not analysis_results:
            return StorePlanningReviewAnalysisFetchResult(
                analyzed_count=0,
                positive_count=0,
                negative_count=0,
                error_message="レビュー分析の結果を読み取れませんでした。",
            )

        review_map = {review.id: review for review in reviews}
        saved_count = 0
        positive_count = 0
        negative_count = 0
        for analysis_result in analysis_results:
            review = review_map.get(analysis_result.review_id)
            if review is None:
                continue
            sentiment = cls._normalized_sentiment(analysis_result.sentiment)
            if sentiment == StorePlanningGoogleMapsReviewAnalysis.Sentiment.POSITIVE:
                positive_count += 1
            if sentiment == StorePlanningGoogleMapsReviewAnalysis.Sentiment.NEGATIVE:
                negative_count += 1
            StorePlanningGoogleMapsReviewAnalysis.objects.update_or_create(
                review=review,
                defaults={
                    "sentiment": sentiment,
                    "sentiment_score": analysis_result.sentiment_score,
                    "one_line_summary": analysis_result.one_line_summary,
                    "issue": analysis_result.issue,
                    "next_action": analysis_result.next_action,
                    "location_insight": analysis_result.location_insight,
                    "model_name": client.model_name,
                    "prompt_version": client.PROMPT_VERSION,
                    "raw_response": analysis_result.raw_response,
                    "analyzed_at": timezone.now(),
                },
            )
            saved_count += 1

        return StorePlanningReviewAnalysisFetchResult(
            analyzed_count=saved_count,
            positive_count=positive_count,
            negative_count=negative_count,
        )

    @staticmethod
    def _normalized_sentiment(
        sentiment: str,
    ) -> StorePlanningGoogleMapsReviewAnalysis.Sentiment:
        allowed_sentiments = StorePlanningGoogleMapsReviewAnalysis.Sentiment.values
        if sentiment in allowed_sentiments:
            return sentiment
        return StorePlanningGoogleMapsReviewAnalysis.Sentiment.NEUTRAL

    @staticmethod
    def _fetch_error_message(
        status_code: int, detail: str = "", operation: str = ""
    ) -> str:
        detail_message = f" Google API応答: {detail}" if detail else ""
        operation_message = f" 失敗箇所: {operation}。" if operation else ""
        if status_code == 403:
            return (
                "Google Maps 側でレビュー取得が拒否されました。"
                "APIキーのアプリケーション制限、API制限、Places APIの有効化、課金状態を確認してください。"
                f"{operation_message}"
                f"{detail_message}"
            )
        return (
            "レビュー取得中にエラーが発生しました。時間をおいて再度お試しください。"
            f"{operation_message}"
            f"{detail_message}"
        )

    @classmethod
    def _fetch_error_url(cls, status_code: int) -> str:
        if status_code == 403:
            return cls.GCP_CREDENTIALS_URL
        return ""

    @classmethod
    def _place_details_for_reviews(
        cls, client: GoogleMapsReviewClient, place_vos: list
    ):
        detail_place_vos = []
        for place_vo in place_vos[: cls.MAX_DETAIL_PLACES]:
            detail_place_vo = client.place_details(
                place_id=place_vo.place_id,
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
            place_id = place_vo.place_id
            if place_id in seen_place_ids:
                continue
            seen_place_ids.add(place_id)
            unique_place_vos.append(place_vo)
        return unique_place_vos

    @classmethod
    def _exclude_target_store_place(
        cls, place_vos: list, target_location: StorePlanningTargetLocation
    ) -> list:
        target_name = cls._normalize_name(target_location.name)
        return [
            place_vo
            for place_vo in place_vos
            if cls._normalize_name(place_vo.name or "") != target_name
        ]

    @staticmethod
    def _normalize_name(value: str) -> str:
        return value.lower().replace(" ", "").replace("　", "")

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
        cls,
        target_location: StorePlanningTargetLocation,
        review_scope: str | None = TARGET_STORE_SCOPE,
    ) -> StorePlanningReviewSummary:
        if target_location.latitude is None or target_location.longitude is None:
            return cls._empty_summary()

        cell_rows = cls._empty_cell_rows()
        latest_reviews_by_place = {}
        review_count = 0
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

        for review in cls._review_queryset(target_store, review_scope):
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
            review_count += 1
            latest_review = latest_reviews_by_place.get(review.google_place_id)
            if cls._is_newer_review(planning_review, latest_review):
                latest_reviews_by_place[review.google_place_id] = planning_review

            text = review.review_text or ""
            if cls._has_keyword(text, cls.POSITIVE_KEYWORDS):
                positive_count += 1
            if cls._has_keyword(text, cls.NEGATIVE_KEYWORDS):
                negative_count += 1

        latest_reviews = list(latest_reviews_by_place.values())
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
            total_review_count=review_count,
            average_rating=average_rating,
            positive_count=positive_count,
            negative_count=negative_count,
            cells=cells,
            latest_reviews=latest_reviews[:5],
        )

    @staticmethod
    def _is_newer_review(
        review: StorePlanningReview, current_review: StorePlanningReview | None
    ) -> bool:
        if current_review is None:
            return True
        if review.publish_time is None:
            return False
        if current_review.publish_time is None:
            return True
        return review.publish_time > current_review.publish_time

    @classmethod
    def build_place_insights(
        cls,
        target_location: StorePlanningTargetLocation,
        review_scope: str = NEARBY_SAME_BUSINESS_SCOPE,
    ) -> list[StorePlanningPlaceInsight]:
        target_store = StorePlanningTargetStore.objects.filter(
            slug=target_location.slug
        ).first()
        if target_store is None:
            return []

        reviews = list(
            cls._review_queryset(target_store, review_scope)
            .select_related("analysis")
            .order_by("place_name", "-publish_time", "-id")
        )
        grouped_reviews = {}
        for review in reviews:
            grouped_reviews.setdefault(review.google_place_id, []).append(review)

        summary_map = {
            summary.google_place_id: summary
            for summary in StorePlanningGoogleMapsPlaceSummary.objects.filter(
                target_store_slug=target_store.slug,
                review_scope=review_scope,
            )
        }

        insights = []
        for place_reviews in list(grouped_reviews.values())[: cls.MAX_PLACE_INSIGHTS]:
            first_review = place_reviews[0]
            summary = summary_map.get(first_review.google_place_id)
            insights.append(
                StorePlanningPlaceInsight(
                    place_name=first_review.place_name,
                    review_count=len(place_reviews),
                    analyzed_count=1 if summary else 0,
                    positive_count=summary.positive_count if summary else 0,
                    negative_count=summary.negative_count if summary else 0,
                    average_rating=first_review.rating,
                    google_maps_url=cls._review_google_maps_url(first_review),
                    one_line_summary=summary.one_line_summary if summary else "",
                    strength=summary.one_line_summary if summary else "",
                    weakness=summary.issue if summary else "",
                    issue=summary.issue if summary else "",
                    next_action=summary.next_action if summary else "",
                    location_insight=summary.location_insight if summary else "",
                )
            )
        return insights

    @classmethod
    def build_review_map_places(
        cls, target_location: StorePlanningTargetLocation
    ) -> list[dict]:
        """
        対象店舗とレビュー取得済み店舗をGoogle Maps表示用データに変換する。
        """
        if target_location.latitude is None or target_location.longitude is None:
            return []

        target_store = StorePlanningTargetStore.objects.filter(
            slug=target_location.slug
        ).first()
        if target_store is None:
            return []

        places = [
            {
                "place_id": target_location.slug,
                "name": target_location.name,
                "scope_label": "対象店舗",
                "pin_color": "#0d6efd",
                "rating": None,
                "review_count": 0,
                "google_maps_url": target_location.google_maps_url,
                "location": {
                    "lat": target_location.latitude,
                    "lng": target_location.longitude,
                },
            }
        ]
        grouped_reviews = {}
        reviews = cls._review_queryset(
            target_store, cls.NEARBY_SAME_BUSINESS_SCOPE
        ).order_by("place_name", "-publish_time", "-id")
        for review in reviews:
            grouped_reviews.setdefault(review.google_place_id, []).append(review)

        for place_reviews in list(grouped_reviews.values())[: cls.MAX_PLACE_INSIGHTS]:
            first_review = place_reviews[0]
            places.append(
                {
                    "place_id": first_review.google_place_id,
                    "name": first_review.place_name,
                    "scope_label": "周辺同業",
                    "pin_color": "#dc3545",
                    "rating": first_review.rating,
                    "review_count": len(place_reviews),
                    "google_maps_url": cls._review_google_maps_url(first_review),
                    "location": {
                        "lat": first_review.latitude,
                        "lng": first_review.longitude,
                    },
                }
            )
        return places

    @staticmethod
    def _review_google_maps_url(review: StorePlanningGoogleMapsReview) -> str:
        query_params = urlencode(
            {
                "api": "1",
                "query": review.place_name,
                "query_place_id": review.google_place_id,
            }
        )
        return f"https://www.google.com/maps/search/?{query_params}"

    @classmethod
    def _grouped_reviews_for_summary(
        cls, target_store: StorePlanningTargetStore, review_scope: str
    ) -> list[dict]:
        reviews = list(
            cls._review_queryset(target_store, review_scope).order_by(
                "place_name", "-publish_time", "-id"
            )
        )
        grouped_reviews = {}
        for review in reviews:
            grouped_reviews.setdefault(review.google_place_id, []).append(review)

        groups = []
        for place_reviews in list(grouped_reviews.values())[: cls.MAX_PLACE_INSIGHTS]:
            first_review = place_reviews[0]
            groups.append(
                {
                    "google_place_id": first_review.google_place_id,
                    "place_name": first_review.place_name,
                    "rating": first_review.rating,
                    "review_count": len(place_reviews),
                    "reviews": [
                        {
                            "review_id": review.id,
                            "author": review.author,
                            "publish_time": (
                                review.publish_time.isoformat()
                                if review.publish_time
                                else ""
                            ),
                            "review_text": review.review_text,
                        }
                        for review in place_reviews
                    ],
                }
            )
        return groups

    @staticmethod
    def _first_analysis_value(
        analyses: list[StorePlanningGoogleMapsReviewAnalysis], field_name: str
    ) -> str:
        for analysis in analyses:
            value = getattr(analysis, field_name)
            if value:
                return value
        return ""

    @classmethod
    def _review_queryset(
        cls, target_store: StorePlanningTargetStore, review_scope: str | None
    ):
        queryset = StorePlanningGoogleMapsReview.objects.filter(
            target_store_slug=target_store.slug,
        )
        if review_scope is not None:
            queryset = queryset.filter(review_scope=review_scope)
        return (
            queryset.exclude(review_text__isnull=True)
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
