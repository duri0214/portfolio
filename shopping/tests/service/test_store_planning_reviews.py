from types import SimpleNamespace
from unittest.mock import patch

from django.test import TestCase

from gmarker.models import Place
from shopping.domain.service.store_planning_reviews import StorePlanningReviewService
from shopping.domain.valueobject.store_planning import StorePlanningTargetLocation
from shopping.models import StorePlanningGoogleMapsReview, StorePlanningTargetStore


class StorePlanningReviewServiceTest(TestCase):
    def test_fetch_reviews_uses_places_api_and_saves_reviews(self):
        """
        シナリオ:
        - 入力: 対象店舗候補と、レビュー1件を含むPlaces API検索結果。
        - 処理: 出店計画用レビュー取得サービスを実行する。
        - 期待値: 店舗名検索を実行し、shopping用レビューモデルへ保存すること。
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
        search_place_vo = SimpleNamespace(
            place=place,
            location=SimpleNamespace(latitude=35.7935, longitude=139.8150),
            name="近隣カフェ",
            rating=4.6,
            reviews=[],
        )
        detail_place_vo = SimpleNamespace(
            place=place,
            location=SimpleNamespace(latitude=35.7935, longitude=139.8150),
            name="近隣カフェ",
            rating=4.6,
            reviews=[review],
        )
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

        with patch(
            "shopping.domain.service.store_planning_reviews.GoogleMapsService"
        ) as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.text_search.return_value = [search_place_vo]
            mock_service.place_details.return_value = detail_place_vo
            mock_service.last_error_status_code = None

            result = StorePlanningReviewService.fetch_reviews(
                api_key="dummy-key",
                target_location=target_location,
            )

        mock_service_class.assert_called_once_with("dummy-key")
        text_kwargs = mock_service.text_search.call_args.kwargs
        self.assertIn("Chapter Table", text_kwargs["query"])
        self.assertEqual(500, text_kwargs["radius"])
        self.assertIn("places.id", text_kwargs["fields"])
        self.assertNotIn("places.reviews", text_kwargs["fields"])
        mock_service.nearby_search.assert_not_called()
        details_kwargs = mock_service.place_details.call_args.kwargs
        self.assertEqual("place-1", details_kwargs["place_id"])
        self.assertIn("reviews", details_kwargs["fields"])
        self.assertEqual(1, result.place_count)
        self.assertEqual(1, result.review_count)
        saved_review = StorePlanningGoogleMapsReview.objects.get(
            target_store=StorePlanningTargetStore.objects.get(slug="chapter-table"),
            google_place_id="place-1",
        )
        self.assertEqual("おいしいランチでした。", saved_review.review_text)
        self.assertEqual("近隣カフェ", saved_review.place_name)

    def test_fetch_reviews_returns_error_message_when_api_is_forbidden(self):
        """
        シナリオ:
        - 入力: 店舗名検索で403エラーになった状態。
        - 処理: 出店計画用レビュー取得サービスを実行する。
        - 期待値: レビュー0件ではなく、取得エラーメッセージを返すこと。
        """
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

        with patch(
            "shopping.domain.service.store_planning_reviews.GoogleMapsService"
        ) as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.text_search.return_value = []
            mock_service.last_error_status_code = 403

            result = StorePlanningReviewService.fetch_reviews(
                api_key="dummy-key",
                target_location=target_location,
            )

        self.assertEqual(0, result.place_count)
        self.assertEqual(0, result.review_count)
        self.assertEqual(
            (
                "Google Maps 側でレビュー取得が拒否されました。"
                "APIキーのIPホワイトリストを確認してください。"
            ),
            result.error_message,
        )
        self.assertEqual(
            "https://console.cloud.google.com/apis/credentials", result.error_url
        )
        self.assertEqual("GCP 認証情報を開く", result.error_url_label)
        mock_service.place_details.assert_not_called()

    def test_fetch_reviews_skips_api_when_store_slug_reviews_already_exist(self):
        """
        シナリオ:
        - 入力: 対象店舗slugに紐づくレビューが保存済みのDB。
        - 処理: 出店計画用レビュー取得サービスを実行する。
        - 期待値: Places API検索を実行せず、保存済み件数を返すこと。
        """
        target_store = StorePlanningTargetStore.objects.get(slug="chapter-table")
        StorePlanningGoogleMapsReview.objects.create(
            target_store=target_store,
            target_store_slug=target_store.slug,
            google_place_id="place-1",
            place_name="Chapter Table",
            latitude=35.792822,
            longitude=139.8143238,
            rating=4.3,
            author="reviewer",
            review_text="良いお店でした。",
        )
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

        with patch(
            "shopping.domain.service.store_planning_reviews.GoogleMapsService"
        ) as mock_service_class:
            result = StorePlanningReviewService.fetch_reviews(
                api_key="dummy-key",
                target_location=target_location,
            )

        mock_service_class.assert_not_called()
        self.assertTrue(result.skipped)
        self.assertEqual(1, result.place_count)
        self.assertEqual(1, result.review_count)
