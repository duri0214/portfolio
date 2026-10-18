import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from django.test import SimpleTestCase

from gmarker.domain.service.place_candidate_filter import (
    FIELD_MASK,
    FIELD_MASK_WITH_REVIEWS,
    PlaceCandidateFilter,
    PlacesApiClient,
    PlacesApiError,
    PlaceSearchCriteria,
    PlaceSearchCriteriaCatalog,
    RequiredPlaceMissingError,
)


class FakePlacesApiClient:
    def __init__(self, text_places, nearby_places):
        self.text_places = text_places
        self.nearby_places = nearby_places

    def search_text(self, *, query, criteria):
        return self.text_places

    def search_nearby(self, *, place_type, criteria):
        return self.nearby_places


class PlaceCandidateFilterTests(SimpleTestCase):
    def setUp(self):
        self.criteria = PlaceSearchCriteria.from_dict(
            {
                "slug": "test-profile",
                "label": "テスト候補",
                "area_name": "test_area",
                "center": {"lat": 35.6617, "lng": 139.6977},
                "radius_meters": 800,
                "bounds": {
                    "south": 35.65,
                    "north": 35.67,
                    "west": 139.69,
                    "east": 139.71,
                },
                "text_queries": ["クラフトビール 渋谷"],
                "nearby_types": ["bar"],
                "language_code": "ja",
                "region_code": "JP",
                "required_place": {
                    "name_terms": ["TAP&CROWLER"],
                    "address_hint": "東京都渋谷区宇田川町6-20",
                },
            }
        )

    @staticmethod
    def place(
        *,
        place_id="tap-id",
        name="TAP&CROWLER Shibuya",
        address="東京都渋谷区宇田川町6-20",
        latitude=35.6617,
        longitude=139.6977,
        status="OPERATIONAL",
    ):
        location = (
            {"latitude": latitude, "longitude": longitude}
            if latitude is not None and longitude is not None
            else None
        )
        return {
            "id": place_id,
            "displayName": {"text": name},
            "formattedAddress": address,
            "location": location,
            "businessStatus": status,
            "primaryType": "bar",
            "types": ["bar", "point_of_interest"],
            "rating": 4.5,
            "userRatingCount": 100,
            "googleMapsUri": "https://maps.google.com/example",
        }

    @patch("gmarker.domain.service.place_candidate_filter.requests.post")
    def test_places_api_requests_use_criteria_and_deduplicate_results(self, post):
        """
        シナリオ:
        - 入力: 同じ Place ID を返す Text Search と Nearby Search のレスポンス。
        - 処理: criteria を使って PlacesApiClient と候補抽出を実行する。
        - 期待値: エンドポイント、FieldMask、検索条件が正しく使われ、結果が一件に統合されること。
        """
        text_response = MagicMock()
        text_response.json.return_value = {"places": [self.place()]}
        nearby_response = MagicMock()
        nearby_response.json.return_value = {"places": [self.place()]}
        post.side_effect = [text_response, nearby_response]

        result = PlaceCandidateFilter(PlacesApiClient("test-key")).collect(
            self.criteria
        )

        self.assertEqual(1, result["counts"]["candidates"])
        self.assertEqual(
            ["keyword:クラフトビール 渋谷", "type:bar"],
            result["candidates"][0]["matched_queries"],
        )
        self.assertEqual(
            "https://places.googleapis.com/v1/places:searchText",
            post.call_args_list[0].args[0],
        )
        self.assertEqual(
            "https://places.googleapis.com/v1/places:searchNearby",
            post.call_args_list[1].args[0],
        )
        self.assertEqual(
            FIELD_MASK,
            post.call_args_list[0].kwargs["headers"]["X-Goog-FieldMask"],
        )
        self.assertEqual(
            "クラフトビール 渋谷",
            post.call_args_list[0].kwargs["json"]["textQuery"],
        )

    def test_classifies_status_and_location_rules(self):
        """
        シナリオ:
        - 入力: 営業中、営業状態不明、閉店、対象範囲外、座標なしの店舗。
        - 処理: criteria に従って候補を分類する。
        - 期待値: 営業中だけが候補になり、残りが理由付きで手動確認または除外になること。
        """
        places = [
            self.place(),
            self.place(place_id="unknown", name="状態不明", status=None),
            self.place(place_id="closed", name="閉店", status="CLOSED_PERMANENTLY"),
            self.place(place_id="outside", name="範囲外", latitude=35.68),
            self.place(
                place_id="missing", name="座標なし", latitude=None, longitude=None
            ),
        ]

        result = PlaceCandidateFilter(FakePlacesApiClient(places, [])).collect(
            self.criteria
        )

        self.assertEqual(1, result["counts"]["candidates"])
        self.assertEqual(1, result["counts"]["manual_review"])
        self.assertEqual(3, result["counts"]["excluded"])
        self.assertEqual(
            {"business_closed", "outside_target_area", "location_missing"},
            {record["exclusion_reason"] for record in result["excluded"]},
        )

    def test_type_only_result_can_be_enabled_by_criteria(self):
        """
        シナリオ:
        - 入力: type 検索だけで見つかる店舗と include_type_only=True の criteria。
        - 処理: Text Search と Nearby Search の結果を候補へ分類する。
        - 期待値: type 検索だけの店舗も候補に含まれること。
        """
        value = {
            "slug": self.criteria.slug,
            "label": self.criteria.label,
            "area_name": self.criteria.area_name,
            "center": {
                "lat": self.criteria.center_lat,
                "lng": self.criteria.center_lng,
            },
            "radius_meters": self.criteria.radius_meters,
            "bounds": self.criteria.bounds,
            "text_queries": self.criteria.text_queries,
            "nearby_types": self.criteria.nearby_types,
            "include_type_only": True,
            "required_place": None,
        }
        criteria = PlaceSearchCriteria.from_dict(value)
        type_only_place = self.place(place_id="type-only", name="一般的なバー")

        result = PlaceCandidateFilter(
            FakePlacesApiClient([self.place()], [type_only_place])
        ).collect(criteria)

        self.assertEqual(2, result["counts"]["candidates"])
        self.assertEqual(0, result["counts"]["manual_review"])

    def test_optional_required_place_is_not_checked(self):
        """
        シナリオ:
        - 入力: required_place を持たない criteria と、任意の店舗結果。
        - 処理: 候補抽出を実行する。
        - 期待値: 必須店舗の未検出エラーにならず、候補が返ること。
        """
        value = {
            "slug": self.criteria.slug,
            "label": self.criteria.label,
            "area_name": self.criteria.area_name,
            "center": {
                "lat": self.criteria.center_lat,
                "lng": self.criteria.center_lng,
            },
            "radius_meters": self.criteria.radius_meters,
            "bounds": self.criteria.bounds,
            "text_queries": self.criteria.text_queries,
            "nearby_types": self.criteria.nearby_types,
        }
        criteria = PlaceSearchCriteria.from_dict(value)

        result = PlaceCandidateFilter(
            FakePlacesApiClient([self.place(place_id="other", name="別の店舗")], [])
        ).collect(criteria)

        self.assertEqual(1, result["counts"]["candidates"])

    def test_required_place_must_be_an_operational_candidate(self):
        """
        シナリオ:
        - 入力: required_place に一致しない営業中店舗だけの検索結果。
        - 処理: 候補抽出を実行する。
        - 期待値: 必須店舗未検出エラーになること。
        """
        places = [self.place(place_id="other", name="別のバー")]

        with self.assertRaises(RequiredPlaceMissingError):
            PlaceCandidateFilter(FakePlacesApiClient(places, [])).collect(self.criteria)

    @patch("gmarker.domain.service.place_candidate_filter.requests.post")
    def test_reviews_are_requested_only_when_the_screen_needs_them(self, post):
        """
        シナリオ:
        - 入力: レビューを含む Places API レスポンス。
        - 処理: include_reviews=True で候補抽出する。
        - 期待値: レビューが最大 5 件に整形され、reviews FieldMask が使われること。
        """
        place = self.place()
        place["reviews"] = [
            {
                "text": {"text": "ビールが豊富です"},
                "authorAttribution": {"displayName": "投稿者"},
                "publishTime": "2026-10-18T00:00:00Z",
                "googleMapsUri": "https://maps.google.com/review",
            }
        ]
        text_response = MagicMock()
        text_response.json.return_value = {"places": [place]}
        nearby_response = MagicMock()
        nearby_response.json.return_value = {"places": [place]}
        post.side_effect = [text_response, nearby_response]

        result = PlaceCandidateFilter(
            PlacesApiClient("test-key", field_mask=FIELD_MASK_WITH_REVIEWS)
        ).collect(self.criteria, include_reviews=True)

        self.assertEqual(
            "ビールが豊富です",
            result["candidates"][0]["reviews"][0]["review_text"],
        )
        self.assertEqual("投稿者", result["candidates"][0]["reviews"][0]["author"])
        self.assertEqual(
            FIELD_MASK_WITH_REVIEWS,
            post.call_args_list[0].kwargs["headers"]["X-Goog-FieldMask"],
        )

    def test_display_records_hide_inspection_fields(self):
        """
        シナリオ:
        - 入力: 検索経路と type 判定を含む候補レコード。
        - 処理: 画面表示用レコードへ変換する。
        - 期待値: 店舗とレビューの表示に必要な項目だけが残ること。
        """
        record = {
            "place_id": "place-id",
            "name": "店舗",
            "location": {"lat": 35.66, "lng": 139.69},
            "rating": 4.5,
            "reviews": [],
            "matched_queries": ["keyword:秘密の検索語"],
            "candidate_category": "keyword_and_type",
            "primary_type": "bar",
            "types": ["bar"],
        }

        display_record = PlaceCandidateFilter.to_display_records([record])[0]

        self.assertNotIn("matched_queries", display_record)
        self.assertNotIn("candidate_category", display_record)
        self.assertNotIn("types", display_record)
        self.assertEqual("店舗", display_record["name"])

    def test_catalog_loads_and_resolves_profiles_from_json_files(self):
        """
        シナリオ:
        - 入力: slug と label を持つ criteria JSON ファイル。
        - 処理: カタログの一覧取得と slug 解決を実行する。
        - 期待値: ファイル追加だけで画面用プロフィールが登録されること。
        """
        value = {
            "slug": "new-profile",
            "label": "新しい候補",
            "area_name": "new_area",
            "center": {"lat": 35.0, "lng": 139.0},
            "radius_meters": 500,
            "bounds": {"south": 34.0, "north": 36.0, "west": 138.0, "east": 140.0},
            "text_queries": ["店舗"],
            "nearby_types": ["restaurant"],
        }
        with TemporaryDirectory() as directory:
            path = Path(directory) / "new_profile.json"
            path.write_text(json.dumps(value), encoding="utf-8")

            catalog = PlaceSearchCriteriaCatalog(directory)

            profiles = catalog.all()
            resolved = catalog.resolve("new-profile")

        self.assertEqual(["new-profile"], [profile.slug for profile in profiles])
        self.assertEqual("新しい候補", resolved.label)

    @patch("gmarker.domain.service.place_candidate_filter.requests.post")
    def test_api_errors_are_not_returned_as_empty_results(self, post):
        """
        シナリオ:
        - 入力: Places API の通信エラー。
        - 処理: Text Search を実行する。
        - 期待値: 空結果ではなく PlacesApiError が送出されること。
        """
        post.side_effect = __import__("requests").RequestException("network error")

        with self.assertRaises(PlacesApiError):
            PlacesApiClient("test-key").search_text(
                query="クラフトビール 渋谷", criteria=self.criteria
            )
