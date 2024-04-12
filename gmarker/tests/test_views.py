from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from gmarker.models import SignageMenuName, StoreInformation


class TestView(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.create_user(email="tester@b.c").set_password("12345")
        SignageMenuName.objects.create(menu_code="1A", menu_name="ラーメン")
        SignageMenuName.objects.create(menu_code="1B", menu_name="洋食")
        SignageMenuName.objects.create(menu_code="1C", menu_name="和食")
        StoreInformation.objects.create(
            category=9,
            shop_name="渋谷駅",
            shop_latlng="35.6598003,139.7023894",
            create_at="2023-02-12 00:00:00",
        )
        StoreInformation.objects.create(
            category=3,
            shop_name="忠犬ハチ公像",
            shop_latlng="35.6590439,139.7005917",
            create_at="2023-02-12 00:00:00",
        )
        StoreInformation.objects.create(
            category=3,
            shop_name="明治神宮",
            shop_latlng="35.676236,139.6993411",
            create_at="2023-02-12 00:00:00",
        )

    def test_get_top_page_200(self):
        response = self.client.get(reverse("mrk:index"))
        self.assertEqual(200, response.status_code)
