from unittest.mock import MagicMock, patch

from django.test import TestCase
from django.urls import reverse

from gmarker.domain.service.craft_beer_places import PlacesApiError
from gmarker.models import NearbyPlace, Place


class TestView(TestCase):
    @classmethod
    def setUpTestData(cls):
        # まずPlaceオブジェクトを作成
        place1 = Place.objects.create(
            place_id="ChIJXSModoALGGARILWiCfeu2M0",
            name="渋谷駅",
            location="35.6598003,139.7023894",
        )
        place2 = Place.objects.create(
            place_id="ChIJXSModoALGGARILWiCfeu2M1",
            name="忠犬ハチ公像",
            location="35.6590439,139.7005917",
        )
        place3 = Place.objects.create(
            place_id="ChIJXSModoALGGARILWiCfeu2M2",
            name="明治神宮",
            location="35.676236,139.6993411",
        )

        # NearbyPlaceオブジェクトを作成し、Placeを関連付け
        NearbyPlace.objects.create(
            category=9,
            place=place1,
        )
        NearbyPlace.objects.create(
            category=3,
            place=place2,
        )
        NearbyPlace.objects.create(
            category=3,
            place=place3,
        )

    def test_get_top_page_200(self):
        response = self.client.get(reverse("mrk:index"))
        self.assertEqual(200, response.status_code)

    def test_top_page_shows_craft_beer_candidate_button(self):
        """
        シナリオ:
        - 入力: 初期表示用の中心座標を持つ状態。
        - 処理: gmarker のトップ画面を表示する。
        - 期待値: 専用のクラフトビール候補抽出を送信するボタンが表示されること。
        """
        response = self.client.get(reverse("mrk:index"))

        self.assertContains(response, "クラフトビール候補")
        self.assertContains(response, reverse("mrk:craft_beer_candidates"))

    @patch("gmarker.views.load_config")
    @patch("gmarker.views.CraftBeerPlacesExporter")
    @patch.dict("os.environ", {"GOOGLE_MAPS_BE_API_KEY": "test-key"})
    def test_craft_beer_candidate_search_displays_filtered_candidates(
        self, exporter_class, load_config
    ):
        """
        シナリオ:
        - 入力: 境界・営業状態で抽出済みのクラフトビール候補を返すサービス。
        - 処理: クラフトビール候補ボタンの POST を実行する。
        - 期待値: 一般的な restaurant 検索結果ではなく、抽出済み候補だけが一覧と地図に表示されること。
        """
        config = MagicMock(center_lat=35.6617, center_lng=139.6977)
        load_config.return_value = config
        exporter_class.return_value.collect.return_value = {
            "counts": {"candidates": 1, "manual_review": 2, "excluded": 3},
            "candidates": [
                {
                    "place_id": "craft-beer-id",
                    "name": "TAP&CROWLER Shibuya",
                    "formatted_address": "東京都渋谷区宇田川町6-20",
                    "location": {"lat": 35.6617, "lng": 139.6977},
                    "matched_queries": ["keyword:クラフトビール 渋谷"],
                    "rating": 4.5,
                    "google_maps_uri": "https://maps.google.com/example",
                }
            ],
        }

        response = self.client.post(reverse("mrk:craft_beer_candidates"))

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "TAP&amp;CROWLER Shibuya")
        self.assertNotContains(response, "STARBUCKS RESERVE")
        self.assertContains(response, "候補 1 件 / 手動確認 2 件 / 除外 3 件")
        exporter_class.return_value.collect.assert_called_once_with(config)

    @patch("gmarker.views.load_config")
    @patch("gmarker.views.CraftBeerPlacesExporter")
    @patch.dict("os.environ", {"GOOGLE_MAPS_BE_API_KEY": "test-key"})
    def test_craft_beer_candidate_search_shows_error_when_api_fails(
        self, exporter_class, load_config
    ):
        """
        シナリオ:
        - 入力: Places API エラーを送出する候補抽出サービス。
        - 処理: クラフトビール候補ボタンの POST を実行する。
        - 期待値: 通常の検索結果として扱わず、502と次の操作を示すエラーメッセージを表示すること。
        """
        load_config.return_value = MagicMock()
        exporter_class.return_value.collect.side_effect = PlacesApiError("api error")

        response = self.client.post(reverse("mrk:craft_beer_candidates"))

        self.assertEqual(502, response.status_code)
        self.assertContains(
            response,
            "クラフトビール候補を取得できませんでした。時間を置いて再度実行してください。",
            status_code=502,
        )
