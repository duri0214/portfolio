from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from gmarker.models import Place
from shopping.domain.service.store_planning_reviews import StorePlanningReviewService
from shopping.domain.valueobject.store_planning import StorePlanningTargetLocation


class StorePlanningReviewServiceTest(TestCase):
    def test_fetch_reviews_uses_places_api_and_saves_reviews(self):
        """
        シナリオ:
        - 入力: 対象店舗候補と、レビュー1件を含むPlaces API検索結果。
        - 処理: 出店計画用レビュー取得サービスを実行する。
        - 期待値: 半径500m・飲食系type・レビュー取得fieldで検索し、PlaceReview保存処理へ渡すこと。
        """
        place = Place.objects.create(
            place_id="place-1",
            name="近隣カフェ",
            location="35.7935,139.8150",
            rating=4.6,
        )
        review = SimpleNamespace(
            text="おいしいランチでした。",
            author="reviewer",
            publish_time="2026-01-01T00:00:00Z",
            google_maps_uri="https://maps.google.com/example",
        )
        place_vo = SimpleNamespace(place=place, reviews=[review])
        target_location = StorePlanningTargetLocation(
            slug="chapter-table",
            name="Chapter Table",
            address="東京都足立区東保木間二丁目",
            latitude=35.792822,
            longitude=139.8143238,
            city_code="13121",
            town_code="073002",
            population_area="東京都足立区東保木間二丁目",
        )

        with (
            patch(
                "shopping.domain.service.store_planning_reviews.GoogleMapsService"
            ) as mock_service_class,
            patch(
                "shopping.domain.service.store_planning_reviews.PlaceReviewRepository.bulk_create"
            ) as mock_bulk_create,
        ):
            mock_service = mock_service_class.return_value
            mock_service.nearby_search.return_value = [place_vo]

            result = StorePlanningReviewService.fetch_reviews(
                api_key="dummy-key",
                target_location=target_location,
            )

        mock_service_class.assert_called_once_with("dummy-key")
        kwargs = mock_service.nearby_search.call_args.kwargs
        self.assertEqual(500, kwargs["radius"])
        self.assertEqual(
            ["restaurant", "cafe", "bar", "bakery"], kwargs["search_types"]
        )
        self.assertIn("places.reviews", kwargs["fields"])
        self.assertEqual(1, result.place_count)
        self.assertEqual(1, result.review_count)
        saved_reviews = mock_bulk_create.call_args.args[0]
        self.assertEqual(1, len(saved_reviews))
        self.assertEqual("おいしいランチでした。", saved_reviews[0].review_text)
        self.assertEqual(place, saved_reviews[0].place)
