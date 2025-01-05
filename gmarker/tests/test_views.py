from django.test import TestCase
from django.urls import reverse

from gmarker.models import NearbyPlace


class TestView(TestCase):
    @classmethod
    def setUpTestData(cls):
        NearbyPlace.objects.create(
            category=9,
            name="渋谷駅",
            location="35.6598003,139.7023894",
            created_at="2023-02-12 00:00:00",
        )
        NearbyPlace.objects.create(
            category=3,
            name="忠犬ハチ公像",
            location="35.6590439,139.7005917",
            created_at="2023-02-12 00:00:00",
        )
        NearbyPlace.objects.create(
            category=3,
            name="明治神宮",
            location="35.676236,139.6993411",
            created_at="2023-02-12 00:00:00",
        )

    def test_get_top_page_200(self):
        response = self.client.get(reverse("mrk:index"))
        self.assertEqual(200, response.status_code)
