import csv
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from gmarker.domain.service.craft_beer_places import (
    FIELD_MASK,
    CraftBeerExportConfig,
    CraftBeerPlacesExporter,
    PlacesApiClient,
    PlacesApiError,
    RequiredPlaceMissingError,
    write_output,
)


class FakePlacesApiClient:
    def __init__(self, text_places, nearby_places):
        self.text_places = text_places
        self.nearby_places = nearby_places

    def search_text(self, *, query, config):
        return self.text_places

    def search_nearby(self, *, place_type, config):
        return self.nearby_places


class CraftBeerPlacesExporterTests(SimpleTestCase):
    def setUp(self):
        self.config = CraftBeerExportConfig.from_dict(
            {
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

    @patch("gmarker.domain.service.craft_beer_places.requests.post")
    def test_places_api_requests_use_new_endpoints_field_mask_and_deduplicate(
        self, post
    ):
        """
        シナリオ:
        - 入力: 同じ Place ID を Text Search と Nearby Search が返すモックレスポンス。
        - 処理: PlacesApiClient を通じて候補抽出を実行する。
        - 期待値: New API の各エンドポイント・FieldMask・リクエスト本文を使い、候補は1件に統合されること。
        """
        text_response = MagicMock()
        text_response.json.return_value = {"places": [self.place()]}
        nearby_response = MagicMock()
        nearby_response.json.return_value = {"places": [self.place()]}
        post.side_effect = [text_response, nearby_response]

        result = CraftBeerPlacesExporter(PlacesApiClient("test-key")).collect(
            self.config
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
            FIELD_MASK, post.call_args_list[0].kwargs["headers"]["X-Goog-FieldMask"]
        )
        self.assertEqual(
            "クラフトビール 渋谷", post.call_args_list[0].kwargs["json"]["textQuery"]
        )
        self.assertEqual(
            ["bar"], post.call_args_list[1].kwargs["json"]["includedTypes"]
        )

    def test_classifies_operational_unknown_closed_outside_and_missing_locations(self):
        """
        シナリオ:
        - 入力: 営業中、営業状態不明、閉店、範囲外、座標欠落の店舗レスポンス。
        - 処理: 抽出結果を候補・手動確認・除外へ分類する。
        - 期待値: 営業中だけが候補、状態不明だけが手動確認、残りは理由付きで除外されること。
        """
        places = [
            self.place(),
            self.place(place_id="unknown", name="状態不明", status=None),
            self.place(place_id="closed", name="閉店", status="CLOSED_PERMANENTLY"),
            self.place(place_id="outside", name="範囲外", latitude=35.68),
            self.place(
                place_id="missing", name="座標欠落", latitude=None, longitude=None
            ),
        ]

        result = CraftBeerPlacesExporter(FakePlacesApiClient(places, [])).collect(
            self.config
        )

        self.assertEqual(1, result["counts"]["candidates"])
        self.assertEqual(1, result["counts"]["manual_review"])
        self.assertEqual(3, result["counts"]["excluded"])
        self.assertTrue(result["candidates"][0]["manual_review_required"])
        self.assertEqual(None, result["candidates"][0]["tap_count"])
        self.assertEqual(
            "unconfirmed", result["candidates"][0]["publication_permission"]
        )
        self.assertEqual(
            {"business_closed", "outside_target_area", "location_missing"},
            {record["exclusion_reason"] for record in result["excluded"]},
        )

    def test_raises_when_required_place_is_not_an_operational_candidate(self):
        """
        シナリオ:
        - 入力: 必須店舗名を含まない営業中の店舗だけを返すモッククライアント。
        - 処理: 候補抽出を実行する。
        - 期待値: 必須候補の未検出を成功として扱わず、RequiredPlaceMissingErrorになること。
        """
        places = [self.place(place_id="other", name="別のビアバー")]

        with self.assertRaises(RequiredPlaceMissingError):
            CraftBeerPlacesExporter(FakePlacesApiClient(places, [])).collect(
                self.config
            )

    def test_sends_type_only_results_to_manual_review(self):
        """
        シナリオ:
        - 入力: 検索語で見つかった必須店舗と、Nearby Search の type だけで見つかった営業中の店舗。
        - 処理: クラフトビール候補を分類する。
        - 期待値: type だけで見つかった店舗は候補一覧へ混ぜず、type_search_only 理由の手動確認になること。
        """
        type_only_place = self.place(place_id="type-only", name="一般的なレストラン")
        result = CraftBeerPlacesExporter(
            FakePlacesApiClient([self.place()], [type_only_place])
        ).collect(self.config)

        self.assertEqual(1, result["counts"]["candidates"])
        self.assertEqual(1, result["counts"]["manual_review"])
        self.assertEqual("type-only", result["manual_review"][0]["place_id"])
        self.assertEqual(
            "type_search_only", result["manual_review"][0]["exclusion_reason"]
        )

    def test_writes_json_and_csv_without_api_key(self):
        """
        シナリオ:
        - 入力: APIキーを含まない抽出結果と一時出力先。
        - 処理: JSON と CSV の両形式を書き出す。
        - 期待値: 必須検品項目を持つファイルが作成され、内容にAPIキーが含まれないこと。
        """
        result = CraftBeerPlacesExporter(
            FakePlacesApiClient([self.place()], [])
        ).collect(self.config)
        with TemporaryDirectory() as directory:
            json_path = Path(directory) / "places.json"
            csv_path = Path(directory) / "places.csv"

            write_output(result=result, output_path=json_path, output_format="json")
            write_output(result=result, output_path=csv_path, output_format="csv")

            json_content = json_path.read_text(encoding="utf-8")
            with csv_path.open(encoding="utf-8-sig", newline="") as output_file:
                csv_rows = list(csv.DictReader(output_file))
        self.assertIn("publication_permission", json_content)
        self.assertNotIn("test-key", json_content)
        self.assertEqual("tap-id", csv_rows[0]["place_id"])
        self.assertEqual("35.6617", csv_rows[0]["location_lat"])

    @patch("gmarker.domain.service.craft_beer_places.requests.post")
    def test_api_error_is_reported_instead_of_returning_empty_results(self, post):
        """
        シナリオ:
        - 入力: HTTP エラーを送出する Places API のモック。
        - 処理: Text Search を実行する。
        - 期待値: 空配列ではなく PlacesApiError で呼び出し失敗が通知されること。
        """
        post.side_effect = __import__("requests").RequestException("network error")

        with self.assertRaises(PlacesApiError):
            PlacesApiClient("test-key").search_text(
                query="クラフトビール 渋谷", config=self.config
            )

    @patch("gmarker.domain.service.craft_beer_places.requests.post")
    def test_invalid_api_response_is_reported_instead_of_returning_empty_results(
        self, post
    ):
        """
        シナリオ:
        - 入力: places 配列を持たない成功HTTPレスポンスのモック。
        - 処理: Text Search を実行する。
        - 期待値: 空配列ではなく PlacesApiError で不正レスポンスが通知されること。
        """
        response = MagicMock()
        response.json.return_value = {}
        post.return_value = response

        with self.assertRaises(PlacesApiError):
            PlacesApiClient("test-key").search_text(
                query="クラフトビール 渋谷", config=self.config
            )

    def test_rejects_an_invalid_nearby_search_type(self):
        """
        シナリオ:
        - 入力: Nearby Search で利用できない type を含む設定値。
        - 処理: CraftBeerExportConfig を生成する。
        - 期待値: 不正な type を無視して実行せず、ValueErrorとなること。
        """
        config = self.config.public_dict()
        config["nearby_types"] = ["invalid_type"]

        with self.assertRaises(ValueError):
            CraftBeerExportConfig.from_dict(config)


class ExportCraftBeerPlacesCommandTests(SimpleTestCase):
    def test_command_fails_before_creating_output_when_required_place_is_missing(self):
        """
        シナリオ:
        - 入力: 必須候補を返さないクライアント、設定ファイル、一時出力先。
        - 処理: export_craft_beer_places コマンドを実行する。
        - 期待値: CommandErrorとなり、成功と誤認できる出力ファイルが作成されないこと。
        """
        config = {
            "area_name": "test_area",
            "center": {"lat": 35.6617, "lng": 139.6977},
            "radius_meters": 800,
            "bounds": {"south": 35.65, "north": 35.67, "west": 139.69, "east": 139.71},
            "text_queries": ["クラフトビール 渋谷"],
            "nearby_types": ["bar"],
            "required_place": {
                "name_terms": ["TAP&CROWLER"],
                "address_hint": "宇田川町",
            },
        }
        with TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.json"
            output_path = Path(directory) / "places.json"
            config_path.write_text(json.dumps(config), encoding="utf-8")
            client = FakePlacesApiClient([], [])

            with (
                patch.dict(os.environ, {"GOOGLE_MAPS_BE_API_KEY": "test-key"}),
                patch(
                    "gmarker.management.commands.export_craft_beer_places.PlacesApiClient",
                    return_value=client,
                ),
                self.assertRaises(CommandError),
            ):
                call_command(
                    "export_craft_beer_places",
                    "--config",
                    str(config_path),
                    "--format",
                    "json",
                    "--output",
                    str(output_path),
                )

            self.assertFalse(output_path.exists())
