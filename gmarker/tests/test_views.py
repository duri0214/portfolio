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
