from unittest.mock import patch

from django.test import TestCase

from lib.geo.valueobject.coord import GoogleMapsCoord
from shopping.domain.service.store_planning_reviews import StorePlanningReviewService
from shopping.domain.valueobject.google_maps_reviews import (
    GoogleMapsPlaceData,
    GoogleMapsReviewData,
)
from shopping.domain.valueobject.store_planning import StorePlanningTargetLocation
from shopping.domain.valueobject.store_planning_reviews import (
    StorePlanningReviewAnalysisResult,
)
from shopping.models import (
    StorePlanningGoogleMapsReview,
    StorePlanningGoogleMapsReviewAnalysis,
    StorePlanningTargetStore,
)


class StorePlanningReviewServiceTest(TestCase):
    def test_fetch_reviews_uses_places_api_and_saves_reviews(self):
        """
        シナリオ:
        - 入力: 対象店舗候補と、レビュー1件を含むPlaces API検索結果。
        - 処理: 出店計画用レビュー取得サービスを実行する。
        - 期待値: 店舗名検索を実行し、shopping用レビューモデルへ保存すること。
        """
        review = GoogleMapsReviewData(
            text="おいしいランチでした。",
            author="reviewer",
            publish_time="2026-01-01T00:00:00Z",
            google_maps_uri="https://maps.google.com/example",
        )
        search_place_vo = GoogleMapsPlaceData(
            place_id="place-1",
            location=GoogleMapsCoord(35.7935, 139.8150),
            name="近隣カフェ",
            rating=4.6,
            reviews=[],
        )
        detail_place_vo = GoogleMapsPlaceData(
            place_id="place-1",
            location=GoogleMapsCoord(35.7935, 139.8150),
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
            "shopping.domain.service.store_planning_reviews.GoogleMapsReviewClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.text_search.return_value = [search_place_vo]
            mock_client.place_details.return_value = detail_place_vo
            mock_client.last_error_status_code = None

            result = StorePlanningReviewService.fetch_reviews(
                api_key="dummy-key",
                target_location=target_location,
            )

        mock_client_class.assert_called_once_with("dummy-key")
        text_kwargs = mock_client.text_search.call_args.kwargs
        self.assertIn("Chapter Table", text_kwargs["query"])
        self.assertEqual(500, text_kwargs["radius"])
        self.assertIn("places.id", text_kwargs["fields"])
        self.assertNotIn("places.reviews", text_kwargs["fields"])
        details_kwargs = mock_client.place_details.call_args.kwargs
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
            "shopping.domain.service.store_planning_reviews.GoogleMapsReviewClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.text_search.return_value = []
            mock_client.last_error_status_code = 403

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
        mock_client.place_details.assert_not_called()

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
            "shopping.domain.service.store_planning_reviews.GoogleMapsReviewClient"
        ) as mock_client_class:
            result = StorePlanningReviewService.fetch_reviews(
                api_key="dummy-key",
                target_location=target_location,
            )

        mock_client_class.assert_not_called()
        self.assertTrue(result.skipped)
        self.assertEqual(1, result.place_count)
        self.assertEqual(1, result.review_count)

    def test_fetch_nearby_same_business_reviews_saves_reviews_with_separate_scope(self):
        """
        シナリオ:
        - 入力: 対象店舗と同じ業態の周辺店舗検索結果と、対象店舗レビューが保存済みのDB。
        - 処理: 周辺同業店舗レビュー取得サービスを実行する。
        - 期待値: 対象店舗レビューと混ざらない種別で周辺同業レビューを保存すること。
        """
        target_store = StorePlanningTargetStore.objects.get(slug="chapter-table")
        StorePlanningGoogleMapsReview.objects.create(
            target_store=target_store,
            target_store_slug=target_store.slug,
            review_scope=StorePlanningGoogleMapsReview.ReviewScope.TARGET_STORE,
            google_place_id="target-place",
            place_name="Chapter Table",
            latitude=35.792822,
            longitude=139.8143238,
            rating=4.3,
            author="target-reviewer",
            review_text="対象店舗のレビューです。",
        )
        review = GoogleMapsReviewData(
            text="近くで使いやすいカフェでした。",
            author="nearby-reviewer",
            publish_time="2026-01-02T00:00:00Z",
            google_maps_uri="https://maps.google.com/nearby",
        )
        search_place_vo = GoogleMapsPlaceData(
            place_id="nearby-place",
            location=GoogleMapsCoord(35.7930, 139.8147),
            name="近隣カフェ",
            rating=4.1,
            reviews=[],
        )
        detail_place_vo = GoogleMapsPlaceData(
            place_id="nearby-place",
            location=GoogleMapsCoord(35.7930, 139.8147),
            name="近隣カフェ",
            rating=4.1,
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
            business_type_label="カフェ",
            business_search_query="カフェ",
        )

        with patch(
            "shopping.domain.service.store_planning_reviews.GoogleMapsReviewClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.text_search.return_value = [search_place_vo]
            mock_client.place_details.return_value = detail_place_vo
            mock_client.last_error_status_code = None

            result = StorePlanningReviewService.fetch_nearby_same_business_reviews(
                api_key="dummy-key",
                target_location=target_location,
            )

        text_kwargs = mock_client.text_search.call_args.kwargs
        self.assertIn("カフェ", text_kwargs["query"])
        self.assertIn("東京都足立区東保木間二丁目", text_kwargs["query"])
        self.assertEqual(1, result.place_count)
        self.assertEqual(1, result.review_count)
        nearby_review = StorePlanningGoogleMapsReview.objects.get(
            target_store=target_store,
            google_place_id="nearby-place",
        )
        self.assertEqual(
            StorePlanningGoogleMapsReview.ReviewScope.NEARBY_SAME_BUSINESS,
            nearby_review.review_scope,
        )
        target_summary = StorePlanningReviewService.build_summary(
            target_location,
            review_scope=StorePlanningReviewService.TARGET_STORE_SCOPE,
        )
        nearby_summary = StorePlanningReviewService.build_summary(
            target_location,
            review_scope=StorePlanningReviewService.NEARBY_SAME_BUSINESS_SCOPE,
        )
        self.assertEqual(1, target_summary.total_review_count)
        self.assertEqual(1, nearby_summary.total_review_count)

    def test_analyze_nearby_same_business_reviews_saves_child_analysis_once(self):
        """
        シナリオ:
        - 入力: 未分析の周辺同業レビューが保存済みのDBとLLM分析結果。
        - 処理: 周辺同業レビュー分析サービスを実行する。
        - 期待値: レビュー子テーブルへ分析結果を保存し、再実行時はLLMを呼ばないこと。
        """
        target_store = StorePlanningTargetStore.objects.get(slug="chapter-table")
        review = StorePlanningGoogleMapsReview.objects.create(
            target_store=target_store,
            target_store_slug=target_store.slug,
            review_scope=StorePlanningGoogleMapsReview.ReviewScope.NEARBY_SAME_BUSINESS,
            google_place_id="nearby-place",
            place_name="近隣カフェ",
            latitude=35.7930,
            longitude=139.8147,
            rating=4.1,
            author="nearby-reviewer",
            review_text="雰囲気は良いが席が狭いです。",
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
            business_type_label="カフェ",
            business_search_query="カフェ",
        )

        with patch(
            "shopping.domain.service.store_planning_reviews.GoogleMapsReviewAnalysisClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.model_name = "gpt-5-mini"
            mock_client.PROMPT_VERSION = "test-prompt"
            mock_client.analyze_reviews.return_value = [
                StorePlanningReviewAnalysisResult(
                    review_id=review.id,
                    sentiment="negative",
                    sentiment_score=-40,
                    one_line_summary="雰囲気は良いが席の狭さが課題。",
                    issue="席が狭い",
                    next_action="席間隔を差別化要素として検討する",
                    location_insight="近隣では滞在快適性に改善余地がある",
                    raw_response={"review_id": review.id},
                )
            ]

            result = StorePlanningReviewService.analyze_nearby_same_business_reviews(
                api_key="dummy-key",
                target_location=target_location,
            )
            skipped_result = (
                StorePlanningReviewService.analyze_nearby_same_business_reviews(
                    api_key="dummy-key",
                    target_location=target_location,
                )
            )

        mock_client.analyze_reviews.assert_called_once()
        self.assertEqual(1, result.analyzed_count)
        self.assertEqual(0, result.positive_count)
        self.assertEqual(1, result.negative_count)
        self.assertTrue(skipped_result.skipped)
        analysis = StorePlanningGoogleMapsReviewAnalysis.objects.get(review=review)
        self.assertEqual(
            StorePlanningGoogleMapsReviewAnalysis.Sentiment.NEGATIVE,
            analysis.sentiment,
        )
        self.assertEqual("席が狭い", analysis.issue)
        insights = StorePlanningReviewService.build_place_insights(target_location)
        self.assertEqual(1, len(insights))
        self.assertEqual("近隣カフェ", insights[0].place_name)
        self.assertEqual("席が狭い", insights[0].issue)
