from datetime import UTC
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from lib.geo.valueobject.coord import GoogleMapsCoord
from shopping.domain.dataprovider.google_maps_review_analysis import (
    GoogleMapsReviewAnalysisClient,
)
from shopping.domain.service.store_planning_reviews import StorePlanningReviewService
from shopping.domain.valueobject.google_maps_reviews import (
    GoogleMapsPlaceData,
    GoogleMapsReviewData,
)
from shopping.domain.valueobject.store_planning import StorePlanningTargetLocation
from shopping.domain.valueobject.store_planning_reviews import (
    StorePlanningPlaceSummaryResult,
)
from shopping.models import (
    StorePlanningGoogleMapsReview,
    StorePlanningGoogleMapsPlaceSummary,
    StorePlanningTargetStore,
)


class GoogleMapsReviewAnalysisClientTest(TestCase):
    def test_parse_results_skips_invalid_review_id_and_defaults_invalid_score(self):
        """
        シナリオ:
        - 入力: LLMが不正なreview_idや数値でないsentiment_scoreを返すJSON。
        - 処理: レビュー分析レスポンスをパースする。
        - 期待値: 不正IDはスキップし、不正スコアは0として扱うこと。
        """
        results = GoogleMapsReviewAnalysisClient._parse_results(
            """
            [
              {"review_id": "bad", "sentiment_score": 80},
              {"review_id": "12", "sentiment_score": "strong", "sentiment": "positive"}
            ]
            """
        )

        self.assertEqual(1, len(results))
        self.assertEqual(12, results[0].review_id)
        self.assertEqual(0, results[0].sentiment_score)

    def test_parse_place_summary_results_defaults_invalid_counts(self):
        """
        シナリオ:
        - 入力: LLMが数値でない店舗サマリー件数を返すJSON。
        - 処理: 店舗単位分析レスポンスをパースする。
        - 期待値: 不正な数値は0として扱い、500エラーにしないこと。
        """
        results = GoogleMapsReviewAnalysisClient._parse_place_summary_results(
            """
            [
              {
                "google_place_id": "place-1",
                "sentiment_score": "good",
                "positive_count": "many",
                "negative_count": null
              }
            ]
            """
        )

        self.assertEqual(1, len(results))
        self.assertEqual(0, results[0].sentiment_score)
        self.assertEqual(0, results[0].positive_count)
        self.assertEqual(0, results[0].negative_count)

    def test_place_summary_prompt_requires_all_places_and_exact_place_id(self):
        """
        シナリオ:
        - 入力: 店舗単位分析の対象グループ。
        - 処理: LLMへ渡すプロンプトを作成する。
        - 期待値: 店舗省略禁止とPlace IDの完全コピーを明示すること。
        """
        client = GoogleMapsReviewAnalysisClient.__new__(GoogleMapsReviewAnalysisClient)

        prompt = client._place_summary_prompt(
            [
                {
                    "google_place_id": "place-1",
                    "place_name": "GRATIALLIGO",
                    "reviews": [{"review_text": "良い店でした。"}],
                }
            ]
        )

        self.assertIn("全店舗について必ず1件ずつ返してください", prompt)
        self.assertIn("google_place_id は入力の値を一字一句そのままコピー", prompt)


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
            mock_client.last_error_operation = "Text Search"
            mock_client.last_error_message = (
                "PERMISSION_DENIED: API key not allowed to use Places API"
            )

            result = StorePlanningReviewService.fetch_reviews(
                api_key="dummy-key",
                target_location=target_location,
            )

        self.assertEqual(0, result.place_count)
        self.assertEqual(0, result.review_count)
        self.assertEqual(
            (
                "Google Maps 側でレビュー取得が拒否されました。"
                "APIキーのアプリケーション制限、API制限、Places APIの有効化、課金状態を確認してください。"
                " 失敗箇所: Text Search。"
                " Google API応答: PERMISSION_DENIED: API key not allowed to use Places API"
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
        StorePlanningGoogleMapsPlaceSummary.objects.create(
            target_store=target_store,
            target_store_slug=target_store.slug,
            review_scope=StorePlanningGoogleMapsReview.ReviewScope.TARGET_STORE,
            google_place_id="place-1",
            place_name="Chapter Table",
            rating=4.3,
            review_count=1,
            positive_count=1,
            negative_count=0,
            sentiment_score=30,
            one_line_summary="古いサマリー",
            issue="古い課題",
            location_insight="古い立地示唆",
            model_name="gpt-5-mini",
            prompt_version="old-prompt",
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

    def test_fetch_reviews_force_refetch_calls_api_when_reviews_already_exist(self):
        """
        シナリオ:
        - 入力: 対象店舗slugに紐づくレビューが保存済みのDBと、再取得指定。
        - 処理: 出店計画用レビュー取得サービスを実行する。
        - 期待値: 保存済みレビューがあってもPlaces API検索を実行すること。
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
        review = GoogleMapsReviewData(
            text="再取得したレビューです。",
            author="new-reviewer",
            publish_time="2026-01-03T00:00:00Z",
            google_maps_uri="https://maps.google.com/new",
        )
        search_place_vo = GoogleMapsPlaceData(
            place_id="place-1",
            location=GoogleMapsCoord(35.792822, 139.8143238),
            name="Chapter Table",
            rating=4.4,
            reviews=[],
        )
        detail_place_vo = GoogleMapsPlaceData(
            place_id="place-1",
            location=GoogleMapsCoord(35.792822, 139.8143238),
            name="Chapter Table",
            rating=4.4,
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
                force_refetch=True,
            )

        mock_client.text_search.assert_called_once()
        self.assertFalse(result.skipped)
        self.assertEqual(1, result.review_count)
        self.assertEqual(1, StorePlanningGoogleMapsReview.objects.count())
        self.assertFalse(StorePlanningGoogleMapsPlaceSummary.objects.exists())
        self.assertTrue(
            StorePlanningGoogleMapsReview.objects.filter(
                target_store=target_store,
                google_place_id="place-1",
                author="new-reviewer",
                review_text="再取得したレビューです。",
            ).exists()
        )

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

    def test_fetch_nearby_same_business_reviews_retries_when_existing_reviews_are_blank(
        self,
    ):
        """
        シナリオ:
        - 入力: 本文が空の周辺同業レビューだけが保存済みのDBと、本文ありレビューを含むPlaces API検索結果。
        - 処理: 周辺同業店舗レビュー取得サービスを実行する。
        - 期待値: 空本文レビューを取得済み扱いにせず、APIを再実行して画面表示対象のレビューを保存すること。
        """
        target_store = StorePlanningTargetStore.objects.get(slug="chapter-table")
        StorePlanningGoogleMapsReview.objects.create(
            target_store=target_store,
            target_store_slug=target_store.slug,
            review_scope=StorePlanningGoogleMapsReview.ReviewScope.NEARBY_SAME_BUSINESS,
            google_place_id="blank-place",
            place_name="空本文カフェ",
            latitude=35.7930,
            longitude=139.8147,
            rating=4.1,
            author="blank-reviewer",
            review_text="",
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

        mock_client.text_search.assert_called_once()
        self.assertFalse(result.skipped)
        self.assertEqual(1, result.review_count)
        nearby_summary = StorePlanningReviewService.build_summary(
            target_location,
            review_scope=StorePlanningReviewService.NEARBY_SAME_BUSINESS_SCOPE,
        )
        self.assertEqual(1, nearby_summary.total_review_count)
        self.assertEqual("近隣カフェ", nearby_summary.latest_reviews[0].place_name)

    def test_build_summary_displays_one_representative_row_per_place(self):
        """
        シナリオ:
        - 入力: 同じ店舗に複数のGoogle Mapsレビューが保存済みのDB。
        - 処理: 出店計画画面用のレビュー集約を作成する。
        - 期待値: 保存レビュー数は複数件として数えつつ、店舗単位の表示用データは1店舗1行になること。
        """
        target_store = StorePlanningTargetStore.objects.get(slug="chapter-table")
        older_time = timezone.datetime(2026, 1, 1, tzinfo=UTC)
        newer_time = timezone.datetime(2026, 1, 2, tzinfo=UTC)
        for author, review_text, publish_time in [
            ("reviewer-old", "古いレビューです。", older_time),
            ("reviewer-new", "新しいレビューです。", newer_time),
        ]:
            StorePlanningGoogleMapsReview.objects.create(
                target_store=target_store,
                target_store_slug=target_store.slug,
                google_place_id="same-place",
                place_name="同じ店舗",
                latitude=35.7930,
                longitude=139.8147,
                rating=4.1,
                author=author,
                review_text=review_text,
                publish_time=publish_time,
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

        summary = StorePlanningReviewService.build_summary(target_location)

        self.assertEqual(1, summary.total_place_count)
        self.assertEqual(2, summary.total_review_count)
        self.assertEqual(1, len(summary.latest_reviews))
        self.assertEqual("同じ店舗", summary.latest_reviews[0].place_name)
        self.assertEqual("新しいレビューです。", summary.latest_reviews[0].review_text)

    def test_analyze_nearby_same_business_reviews_saves_place_summary_once(self):
        """
        シナリオ:
        - 入力: 未分析の周辺同業レビューが保存済みのDBとLLM分析結果。
        - 処理: 周辺同業レビュー分析サービスを実行する。
        - 期待値: 店舗単位のサマリーテーブルへ分析結果を保存し、再実行時はLLMを呼ばないこと。
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
            mock_client.analyze_place_summaries.return_value = [
                StorePlanningPlaceSummaryResult(
                    google_place_id=review.google_place_id,
                    sentiment_score=-40,
                    positive_count=0,
                    negative_count=1,
                    one_line_summary="落ち着いた雰囲気が評価されている。",
                    issue="席が狭い",
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

        mock_client.analyze_place_summaries.assert_called_once()
        self.assertEqual(1, result.analyzed_count)
        self.assertEqual(0, result.positive_count)
        self.assertEqual(1, result.negative_count)
        self.assertTrue(skipped_result.skipped)
        summary = StorePlanningGoogleMapsPlaceSummary.objects.get(
            google_place_id=review.google_place_id,
            review_scope=StorePlanningReviewService.NEARBY_SAME_BUSINESS_SCOPE,
        )
        self.assertEqual(1, summary.review_count)
        self.assertEqual(-40, summary.sentiment_score)
        self.assertEqual("落ち着いた雰囲気が評価されている。", summary.one_line_summary)
        self.assertEqual("席が狭い", summary.issue)
        insights = StorePlanningReviewService.build_place_insights(target_location)
        self.assertEqual(1, len(insights))
        self.assertEqual("近隣カフェ", insights[0].place_name)
        self.assertEqual("席が狭い", insights[0].issue)

    def test_analyze_nearby_same_business_reviews_prompts_retry_when_llm_omits_place(
        self,
    ):
        """
        シナリオ:
        - 入力: 未分析の周辺同業レビューが保存済みで、LLM分析結果が空のDB。
        - 処理: 周辺同業レビュー分析サービスを実行する。
        - 期待値: フォールバックサマリーを保存せず、再実行を促すこと。
        """
        target_store = StorePlanningTargetStore.objects.get(slug="chapter-table")
        StorePlanningGoogleMapsReview.objects.create(
            target_store=target_store,
            target_store_slug=target_store.slug,
            review_scope=StorePlanningGoogleMapsReview.ReviewScope.NEARBY_SAME_BUSINESS,
            google_place_id="nearby-omitted-place",
            place_name="近隣ビアバー",
            latitude=35.7930,
            longitude=139.8147,
            rating=4.1,
            author="nearby-reviewer",
            review_text="親切で美味しいクラフトビールを楽しめました。",
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
            mock_client.analyze_place_summaries.return_value = []

            result = StorePlanningReviewService.analyze_nearby_same_business_reviews(
                api_key="dummy-key",
                target_location=target_location,
            )

        self.assertEqual(0, result.analyzed_count)
        self.assertIn("もう一度レビュー分析を実行してください", result.error_message)
        self.assertIn("近隣ビアバー", result.error_message)
        self.assertFalse(
            StorePlanningGoogleMapsPlaceSummary.objects.filter(
                google_place_id="nearby-omitted-place",
                review_scope=StorePlanningReviewService.NEARBY_SAME_BUSINESS_SCOPE,
            ).exists()
        )

    def test_analyze_nearby_same_business_reviews_saves_returned_places_and_keeps_missing_for_retry(
        self,
    ):
        """
        シナリオ:
        - 入力: 未分析の周辺同業レビューが2店舗分あり、LLMが1店舗分だけ返すDB。
        - 処理: 周辺同業レビュー分析サービスを実行する。
        - 期待値: 返却済み店舗だけ保存し、未返却店舗は再実行対象として残ること。
        """
        target_store = StorePlanningTargetStore.objects.get(slug="chapter-table")
        for place_id, place_name in [
            ("nearby-returned-place", "近隣カフェ"),
            ("nearby-missing-place", "GRATIALLIGO"),
        ]:
            StorePlanningGoogleMapsReview.objects.create(
                target_store=target_store,
                target_store_slug=target_store.slug,
                review_scope=StorePlanningGoogleMapsReview.ReviewScope.NEARBY_SAME_BUSINESS,
                google_place_id=place_id,
                place_name=place_name,
                latitude=35.7930,
                longitude=139.8147,
                rating=4.1,
                author=f"{place_id}-reviewer",
                review_text="親切で使いやすいお店でした。",
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
            mock_client.analyze_place_summaries.return_value = [
                StorePlanningPlaceSummaryResult(
                    google_place_id="nearby-returned-place",
                    sentiment_score=60,
                    positive_count=1,
                    negative_count=0,
                    one_line_summary="親切さが評価されている。",
                    issue="",
                    location_insight="近隣で日常利用されている。",
                    raw_response={"google_place_id": "nearby-returned-place"},
                )
            ]

            result = StorePlanningReviewService.analyze_nearby_same_business_reviews(
                api_key="dummy-key",
                target_location=target_location,
            )
            first_target_groups = mock_client.analyze_place_summaries.call_args.args[0]
            skipped_result = (
                StorePlanningReviewService.analyze_nearby_same_business_reviews(
                    api_key="dummy-key",
                    target_location=target_location,
                )
            )
            retry_target_groups = mock_client.analyze_place_summaries.call_args.args[0]

        self.assertEqual(1, result.analyzed_count)
        self.assertIn("GRATIALLIGO", result.error_message)
        self.assertTrue(
            StorePlanningGoogleMapsPlaceSummary.objects.filter(
                google_place_id="nearby-returned-place",
                review_scope=StorePlanningReviewService.NEARBY_SAME_BUSINESS_SCOPE,
            ).exists()
        )
        self.assertFalse(
            StorePlanningGoogleMapsPlaceSummary.objects.filter(
                google_place_id="nearby-missing-place",
                review_scope=StorePlanningReviewService.NEARBY_SAME_BUSINESS_SCOPE,
            ).exists()
        )

        self.assertCountEqual(
            ["nearby-returned-place", "nearby-missing-place"],
            [group["google_place_id"] for group in first_target_groups],
        )
        self.assertFalse(skipped_result.skipped)
        self.assertEqual(
            ["nearby-missing-place"],
            [group["google_place_id"] for group in retry_target_groups],
        )

    def test_analyze_place_summaries_limits_target_groups_with_max_places(self):
        """
        シナリオ:
        - 入力: 未分析の周辺同業レビューが3店舗分あるDB。
        - 処理: max_places=2で店舗単位分析サービスを実行する。
        - 期待値: LLMへ渡す店舗グループを2件に絞ること。
        """
        target_store = StorePlanningTargetStore.objects.get(slug="chapter-table")
        for index in range(3):
            StorePlanningGoogleMapsReview.objects.create(
                target_store=target_store,
                target_store_slug=target_store.slug,
                review_scope=StorePlanningGoogleMapsReview.ReviewScope.NEARBY_SAME_BUSINESS,
                google_place_id=f"nearby-place-{index}",
                place_name=f"近隣カフェ{index}",
                latitude=35.7930,
                longitude=139.8147,
                rating=4.1,
                author=f"nearby-reviewer-{index}",
                review_text="親切で使いやすいお店でした。",
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

        def summarize(groups):
            return [
                StorePlanningPlaceSummaryResult(
                    google_place_id=group["google_place_id"],
                    sentiment_score=20,
                    positive_count=1,
                    negative_count=0,
                    one_line_summary="親切さが評価されている。",
                    issue="",
                    location_insight="近隣で日常利用されている。",
                    raw_response={"google_place_id": group["google_place_id"]},
                )
                for group in groups
            ]

        with patch(
            "shopping.domain.service.store_planning_reviews.GoogleMapsReviewAnalysisClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.model_name = "gpt-5-mini"
            mock_client.PROMPT_VERSION = "test-prompt"
            mock_client.analyze_place_summaries.side_effect = summarize

            result = StorePlanningReviewService.analyze_place_summaries(
                api_key="dummy-key",
                target_location=target_location,
                review_scope=StorePlanningReviewService.NEARBY_SAME_BUSINESS_SCOPE,
                max_places=2,
            )

        target_groups = mock_client.analyze_place_summaries.call_args.args[0]
        self.assertEqual(2, len(target_groups))
        self.assertEqual(2, result.analyzed_count)
        self.assertEqual(2, StorePlanningGoogleMapsPlaceSummary.objects.count())

    def test_analyze_place_summaries_accepts_place_with_four_reviews(self):
        """
        シナリオ:
        - 入力: レビューが4件だけ保存済みの周辺同業店舗。
        - 処理: 店舗単位分析サービスを実行する。
        - 期待値: 5件未満でも失敗扱いにせず、review_count=4でサマリーを保存すること。
        """
        target_store = StorePlanningTargetStore.objects.get(slug="chapter-table")
        for index in range(4):
            StorePlanningGoogleMapsReview.objects.create(
                target_store=target_store,
                target_store_slug=target_store.slug,
                review_scope=StorePlanningGoogleMapsReview.ReviewScope.NEARBY_SAME_BUSINESS,
                google_place_id="nearby-four-review-place",
                place_name="GRATIALLIGO",
                latitude=35.7930,
                longitude=139.8147,
                rating=4.5,
                author=f"nearby-reviewer-{index}",
                review_text=f"クラフトビールがおいしいレビュー{index}です。",
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
            mock_client.analyze_place_summaries.return_value = [
                StorePlanningPlaceSummaryResult(
                    google_place_id="nearby-four-review-place",
                    sentiment_score=60,
                    positive_count=4,
                    negative_count=0,
                    one_line_summary="クラフトビールが評価されている。",
                    issue="席数が少ない",
                    location_insight="ゆったり飲む客が集まる立地に適合",
                    raw_response={"google_place_id": "nearby-four-review-place"},
                )
            ]

            result = StorePlanningReviewService.analyze_place_summaries(
                api_key="dummy-key",
                target_location=target_location,
                review_scope=StorePlanningReviewService.NEARBY_SAME_BUSINESS_SCOPE,
            )

        self.assertEqual(1, result.analyzed_count)
        summary = StorePlanningGoogleMapsPlaceSummary.objects.get(
            google_place_id="nearby-four-review-place"
        )
        self.assertEqual(4, summary.review_count)
        self.assertEqual(4, summary.positive_count)

    def test_analyze_nearby_same_business_reviews_truncates_llm_text_fields(self):
        """
        シナリオ:
        - 入力: LLMがDB上限より長い分析文を返すDB。
        - 処理: 周辺同業レビュー分析サービスを実行する。
        - 期待値: 保存前に255文字へ丸め、DBエラーにならないこと。
        """
        target_store = StorePlanningTargetStore.objects.get(slug="chapter-table")
        StorePlanningGoogleMapsReview.objects.create(
            target_store=target_store,
            target_store_slug=target_store.slug,
            review_scope=StorePlanningGoogleMapsReview.ReviewScope.NEARBY_SAME_BUSINESS,
            google_place_id="nearby-long-text-place",
            place_name="近隣カフェ",
            latitude=35.7930,
            longitude=139.8147,
            rating=4.1,
            author="nearby-reviewer",
            review_text="親切で使いやすいお店でした。",
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
        long_text = "あ" * 300

        with patch(
            "shopping.domain.service.store_planning_reviews.GoogleMapsReviewAnalysisClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.model_name = "gpt-5-mini"
            mock_client.PROMPT_VERSION = "test-prompt"
            mock_client.analyze_place_summaries.return_value = [
                StorePlanningPlaceSummaryResult(
                    google_place_id="nearby-long-text-place",
                    sentiment_score=60,
                    positive_count=1,
                    negative_count=0,
                    one_line_summary=long_text,
                    issue=long_text,
                    location_insight=long_text,
                    raw_response={"google_place_id": "nearby-long-text-place"},
                )
            ]

            StorePlanningReviewService.analyze_nearby_same_business_reviews(
                api_key="dummy-key",
                target_location=target_location,
            )

        summary = StorePlanningGoogleMapsPlaceSummary.objects.get(
            google_place_id="nearby-long-text-place",
            review_scope=StorePlanningReviewService.NEARBY_SAME_BUSINESS_SCOPE,
        )
        self.assertEqual(255, len(summary.one_line_summary))
        self.assertEqual(255, len(summary.issue))
        self.assertEqual(255, len(summary.location_insight))

    def test_build_place_insights_limits_nearby_same_business_places_to_ten(self):
        """
        シナリオ:
        - 入力: 周辺同業店舗レビューが11店舗分保存済みのDB。
        - 処理: 周辺同業店舗別インサイトを作成する。
        - 期待値: 新宿など候補が多い地域でも、画面に出す店舗別分析は10店舗までに制限されること。
        """
        target_store = StorePlanningTargetStore.objects.get(slug="chapter-table")
        for index in range(11):
            StorePlanningGoogleMapsReview.objects.create(
                target_store=target_store,
                target_store_slug=target_store.slug,
                review_scope=StorePlanningGoogleMapsReview.ReviewScope.NEARBY_SAME_BUSINESS,
                google_place_id=f"nearby-place-{index}",
                place_name=f"近隣カフェ{index:02}",
                latitude=35.7930,
                longitude=139.8147,
                rating=4.1,
                author=f"nearby-reviewer-{index}",
                review_text="近くで使いやすいカフェでした。",
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

        insights = StorePlanningReviewService.build_place_insights(target_location)

        self.assertEqual(10, len(insights))
        self.assertEqual("近隣カフェ00", insights[0].place_name)
        self.assertEqual("近隣カフェ09", insights[-1].place_name)

    def test_build_review_map_places_uses_single_target_pin_and_nearby_pins(self):
        """
        シナリオ:
        - 入力: 対象店舗レビューと周辺同業レビューが保存済みのDB。
        - 処理: レビュー取得店舗マップ用データを作成する。
        - 期待値: 対象店舗ピンは対象地点の1件だけになり、レビュー由来ピンは周辺同業だけになること。
        """
        target_store = StorePlanningTargetStore.objects.get(slug="chapter-table")
        StorePlanningGoogleMapsReview.objects.create(
            target_store=target_store,
            target_store_slug=target_store.slug,
            review_scope=StorePlanningGoogleMapsReview.ReviewScope.TARGET_STORE,
            google_place_id="target-review-place",
            place_name="Chapter Table Reviews",
            latitude=35.7950,
            longitude=139.8170,
            rating=4.0,
            author="target-reviewer",
            review_text="対象店舗のレビューです。",
        )
        StorePlanningGoogleMapsReview.objects.create(
            target_store=target_store,
            target_store_slug=target_store.slug,
            review_scope=StorePlanningGoogleMapsReview.ReviewScope.NEARBY_SAME_BUSINESS,
            google_place_id="nearby-place",
            place_name="近隣カフェ",
            latitude=35.7930,
            longitude=139.8147,
            rating=4.1,
            author="nearby-reviewer",
            review_text="近くで使いやすいカフェでした。",
            google_maps_uri="https://maps.google.com/review-url",
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

        map_places = StorePlanningReviewService.build_review_map_places(target_location)

        self.assertEqual(2, len(map_places))
        self.assertEqual("Chapter Table Reviews", map_places[0]["name"])
        self.assertEqual("対象店舗", map_places[0]["scope_label"])
        self.assertEqual("target-review-place", map_places[0]["place_id"])
        self.assertEqual(35.7950, map_places[0]["location"]["lat"])
        self.assertEqual(139.8170, map_places[0]["location"]["lng"])
        self.assertEqual(
            "https://www.google.com/maps/search/?api=1&query=Chapter+Table+Reviews&query_place_id=target-review-place",
            map_places[0]["google_maps_url"],
        )
        self.assertEqual("近隣カフェ", map_places[1]["name"])
        self.assertEqual("周辺同業", map_places[1]["scope_label"])
        self.assertEqual(
            "https://www.google.com/maps/search/?api=1&query=%E8%BF%91%E9%9A%A3%E3%82%AB%E3%83%95%E3%82%A7&query_place_id=nearby-place",
            map_places[1]["google_maps_url"],
        )

    def test_build_review_map_places_displays_ten_nearby_places_without_radius_filter(
        self,
    ):
        """
        シナリオ:
        - 入力: 周辺同業店舗レビューが11店舗分保存済みで、一部が500mより外側にあるDB。
        - 処理: レビュー取得店舗マップ用データを作成する。
        - 期待値: 距離では落とさず、対象店舗1件と周辺同業10店舗のピンデータが返ること。
        """
        target_store = StorePlanningTargetStore.objects.get(slug="chapter-table")
        for index in range(11):
            StorePlanningGoogleMapsReview.objects.create(
                target_store=target_store,
                target_store_slug=target_store.slug,
                review_scope=StorePlanningGoogleMapsReview.ReviewScope.NEARBY_SAME_BUSINESS,
                google_place_id=f"nearby-place-{index}",
                place_name=f"近隣カフェ{index:02}",
                latitude=35.8000 + index * 0.001,
                longitude=139.8200 + index * 0.001,
                rating=4.1,
                author=f"nearby-reviewer-{index}",
                review_text="近くで使いやすいカフェでした。",
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

        map_places = StorePlanningReviewService.build_review_map_places(target_location)

        self.assertEqual(11, len(map_places))
        self.assertEqual("対象店舗", map_places[0]["scope_label"])
        self.assertEqual(
            10,
            len([place for place in map_places if place["scope_label"] == "周辺同業"]),
        )
        self.assertEqual("近隣カフェ09", map_places[-1]["name"])

    def test_analyze_all_reviews_saves_one_target_and_ten_nearby_place_summaries(
        self,
    ):
        """
        シナリオ:
        - 入力: 対象店舗1店舗と周辺同業11店舗分のレビューが保存済みのDB。
        - 処理: Google Mapsレビュー分析を実行する。
        - 期待値: サマリー後レコードは対象店舗1件、周辺同業10件の最大11件だけ保存されること。
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
            rating=4.0,
            author="target-reviewer",
            review_text="対象店舗のレビューです。",
        )
        for index in range(11):
            StorePlanningGoogleMapsReview.objects.create(
                target_store=target_store,
                target_store_slug=target_store.slug,
                review_scope=StorePlanningGoogleMapsReview.ReviewScope.NEARBY_SAME_BUSINESS,
                google_place_id=f"nearby-place-{index}",
                place_name=f"近隣カフェ{index:02}",
                latitude=35.7930,
                longitude=139.8147,
                rating=4.1,
                author=f"nearby-reviewer-{index}",
                review_text="近くで使いやすいカフェでした。",
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

        def summarize(groups):
            return [
                StorePlanningPlaceSummaryResult(
                    google_place_id=group["google_place_id"],
                    sentiment_score=20,
                    positive_count=1,
                    negative_count=0,
                    one_line_summary=f"{group['place_name']}の評判サマリー。",
                    issue="課題なし",
                    location_insight="立地上の大きな懸念はない",
                    raw_response={"google_place_id": group["google_place_id"]},
                )
                for group in groups
            ]

        with patch(
            "shopping.domain.service.store_planning_reviews.GoogleMapsReviewAnalysisClient"
        ) as mock_client_class:
            mock_client = mock_client_class.return_value
            mock_client.model_name = "gpt-5-mini"
            mock_client.PROMPT_VERSION = "test-prompt"
            mock_client.analyze_place_summaries.side_effect = summarize

            result = StorePlanningReviewService.analyze_all_reviews(
                api_key="dummy-key",
                target_location=target_location,
            )

        self.assertEqual(11, result.analyzed_count)
        self.assertEqual(11, StorePlanningGoogleMapsPlaceSummary.objects.count())
        self.assertEqual(
            1,
            StorePlanningGoogleMapsPlaceSummary.objects.filter(
                review_scope=StorePlanningReviewService.TARGET_STORE_SCOPE
            ).count(),
        )
        self.assertEqual(
            10,
            StorePlanningGoogleMapsPlaceSummary.objects.filter(
                review_scope=StorePlanningReviewService.NEARBY_SAME_BUSINESS_SCOPE
            ).count(),
        )
