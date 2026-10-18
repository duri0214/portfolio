import os
from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse

from gmarker.domain.service.place_candidate_filter import (
    CriteriaNotFoundError,
    PlacesApiError,
)
from gmarker.models import NearbyPlace, Place


class TestView(TestCase):
    @classmethod
    def setUpTestData(cls):
        place1 = Place.objects.create(
            place_id="ChIJXSModoALGGARILWiCfeu2M0",
            name="渋谷駅",
            location="35.6598003,139.7023894",
        )
        place2 = Place.objects.create(
            place_id="ChIJXSModoALGGARILWiCfeu2M1",
            name="ハチ公公園",
            location="35.6590439,139.7005917",
        )
        place3 = Place.objects.create(
            place_id="ChIJXSModoALGGARILWiCfeu2M2",
            name="明治神宮",
            location="35.676236,139.6993411",
        )

        NearbyPlace.objects.create(category=9, place=place1)
        NearbyPlace.objects.create(category=3, place=place2)
        NearbyPlace.objects.create(category=3, place=place3)

    def test_get_top_page_200(self):
        response = self.client.get(reverse("mrk:index"))

        self.assertEqual(200, response.status_code)

    def test_top_page_shows_registered_candidate_profile_button(self):
        """
        シナリオ:
        - 入力: criteria ディレクトリに登録済みの候補検索プロファイル。
        - 処理: gmarker のトップ画面を表示する。
        - 期待値: プロファイルの label と共通 View の URL が表示されること。
        """
        response = self.client.get(reverse("mrk:index"))

        self.assertContains(response, "クラフトビール候補")
        self.assertContains(
            response,
            reverse(
                "mrk:candidate_search",
                kwargs={"criteria_slug": "shibuya-craft-beer"},
            ),
        )

    @patch("gmarker.views.PlaceSearchCriteriaCatalog.resolve")
    @patch("gmarker.views.PlaceCandidateFilter.collect")
    @patch.dict(os.environ, {"GOOGLE_MAPS_BE_API_KEY": "test-key"})
    def test_common_candidate_view_displays_places_and_reviews(self, collect, resolve):
        """
        シナリオ:
        - 入力: slug に対応する criteria と共通 service の候補結果。
        - 処理: 候補検索 URL を POST する。
        - 期待値: 地図と店舗別レビューが表示され、検品用情報は HTML に含まれないこと。
        """
        criteria = MagicMock(
            slug="test-profile",
            label="テスト候補",
            center_lat=35.6617,
            center_lng=139.6977,
        )
        resolve.return_value = criteria
        collect.return_value = {
            "criteria_slug": "test-profile",
            "label": "テスト候補",
            "counts": {"candidates": 1, "manual_review": 0, "excluded": 0},
            "candidates": [
                {
                    "place_id": "candidate-id",
                    "name": "候補店舗",
                    "formatted_address": "東京都渋谷区",
                    "location": {"lat": 35.6617, "lng": 139.6977},
                    "rating": 4.5,
                    "google_maps_uri": "https://maps.google.com/example",
                    "reviews": [
                        {
                            "author": "投稿者",
                            "review_text": "レビュー本文",
                            "publish_time": "2026-10-18T00:00:00Z",
                        }
                    ],
                    "matched_queries": ["keyword:画面に出してはいけない検索語"],
                    "candidate_category": "keyword_and_type",
                    "primary_type": "bar",
                    "types": ["bar"],
                }
            ],
        }

        response = self.client.post(
            reverse(
                "mrk:candidate_search",
                kwargs={"criteria_slug": "test-profile"},
            )
        )

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "候補店舗")
        self.assertContains(response, "レビュー本文")
        self.assertNotContains(response, "matched_queries")
        self.assertNotContains(response, "画面に出してはいけない検索語")
        resolve.assert_called_once_with("test-profile")
        collect.assert_called_once_with(criteria, include_reviews=True)

    @patch("gmarker.views.PlaceCandidateFilter.collect")
    @patch.dict(os.environ, {"GOOGLE_MAPS_BE_API_KEY": "test-key"})
    def test_legacy_candidate_url_uses_the_registered_profile(self, collect):
        """
        シナリオ:
        - 入力: 既存のクラフトビール候補 URL。
        - 処理: 共通候補検索 View を実行する。
        - 期待値: 既存 URL が新しい criteria の検索へ接続されること。
        """
        collect.return_value = {
            "criteria_slug": "shibuya-craft-beer",
            "label": "クラフトビール候補",
            "counts": {"candidates": 0, "manual_review": 0, "excluded": 0},
            "candidates": [],
        }

        response = self.client.post(reverse("mrk:craft_beer_candidates"))

        self.assertEqual(200, response.status_code)
        self.assertEqual("shibuya-craft-beer", collect.call_args.args[0].slug)

    @patch("gmarker.views.PlaceCandidateFilter.collect")
    @patch.dict(os.environ, {"GOOGLE_MAPS_BE_API_KEY": "test-key"})
    def test_common_candidate_view_returns_error_when_api_fails(self, collect):
        """
        シナリオ:
        - 入力: 共通候補 service が PlacesApiError を送出する。
        - 処理: 候補検索 URL を POST する。
        - 期待値: 成功結果として扱わず、502 と利用者向けエラーを返すこと。
        """
        collect.side_effect = PlacesApiError("api error")

        response = self.client.post(
            reverse(
                "mrk:candidate_search",
                kwargs={"criteria_slug": "shibuya-craft-beer"},
            )
        )

        self.assertEqual(502, response.status_code)
        self.assertContains(
            response,
            "候補店舗を取得できませんでした。時間を置いて再度実行してください。",
            status_code=502,
        )

    @patch.dict(os.environ, {}, clear=True)
    def test_common_candidate_view_returns_error_when_api_key_is_missing(self):
        """
        シナリオ:
        - 入力: バックエンドの Google Maps API キーが未設定。
        - 処理: 候補検索 URL を POST する。
        - 期待値: Places API を成功扱いにせず、503 を返すこと。
        """
        response = self.client.post(
            reverse(
                "mrk:candidate_search",
                kwargs={"criteria_slug": "shibuya-craft-beer"},
            )
        )

        self.assertEqual(503, response.status_code)
        self.assertContains(response, "Google Maps API キー設定", status_code=503)

    @patch("gmarker.views.PlaceSearchCriteriaCatalog.resolve")
    def test_common_candidate_view_returns_error_for_an_invalid_profile(self, resolve):
        """
        シナリオ:
        - 入力: criteria の読み込みが ValueError になるプロファイル。
        - 処理: 候補検索 URL を POST する。
        - 期待値: 成功結果として扱わず、500 を返すこと。
        """
        resolve.side_effect = ValueError("invalid criteria")

        response = self.client.post(
            reverse(
                "mrk:candidate_search",
                kwargs={"criteria_slug": "shibuya-craft-beer"},
            )
        )

        self.assertEqual(500, response.status_code)
        self.assertContains(
            response, "候補検索プロファイルに問題があります", status_code=500
        )

    @patch("gmarker.views.PlaceSearchCriteriaCatalog.resolve")
    def test_common_candidate_view_returns_not_found_for_an_unknown_profile(
        self, resolve
    ):
        """
        シナリオ:
        - 入力: カタログに存在しない criteria slug。
        - 処理: 候補検索 URL を POST する。
        - 期待値: 成功結果として扱わず、404 を返すこと。
        """
        resolve.side_effect = CriteriaNotFoundError("missing-profile")

        response = self.client.post(
            reverse(
                "mrk:candidate_search",
                kwargs={"criteria_slug": "missing-profile"},
            )
        )

        self.assertEqual(404, response.status_code)
        self.assertContains(
            response, "候補検索プロファイルが見つかりません", status_code=404
        )
