from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

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
        - 期待値: bar、pub、restaurant を検索するクラフトビール候補ボタンが表示されること。
        """
        response = self.client.get(reverse("mrk:index"))

        self.assertContains(response, "クラフトビール候補")
        self.assertContains(response, "submitSearchForm(1, 'bar,pub,restaurant')")

    @patch("gmarker.views.GoogleMapsService")
    def test_craft_beer_candidate_search_uses_bar_pub_and_restaurant(
        self, service_class
    ):
        """
        シナリオ:
        - 入力: クラフトビール候補ボタンが送る bar,pub,restaurant の検索種別。
        - 処理: カテゴリ検索の POST を実行する。
        - 期待値: Nearby Search に3つの有効 type が渡され、検索結果画面へリダイレクトすること。
        """
        service_class.return_value.nearby_search.return_value = []

        response = self.client.post(
            reverse("mrk:nearby_search", kwargs={"search_code": 1}),
            {"search_types": "bar,pub,restaurant"},
        )

        self.assertRedirects(
            response,
            reverse("mrk:nearby_search", kwargs={"search_code": 1}),
        )
        self.assertEqual(
            ["bar", "pub", "restaurant"],
            service_class.return_value.nearby_search.call_args.kwargs["search_types"],
        )
