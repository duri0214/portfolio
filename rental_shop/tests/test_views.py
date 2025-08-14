from django.test import TestCase
from django.urls import reverse

from rental_shop.models import Warehouse, Staff, WarehouseStaff


class TestView(TestCase):
    @classmethod
    def setUpTestData(cls):
        # 倉庫を作成
        warehouse = Warehouse.objects.create(
            code="iru-ma",
            name="入間倉庫",
            address="埼玉県狭山市稲荷山２丁目３",
            width=3,
            height=3,
            depth=3,
            created_at="2023-02-12 00:00:00",
        )
        # スタッフを作成
        staff = Staff.objects.create(name="スタッフ1", created_at="2023-02-12 00:00:00")
        # 倉庫とスタッフを関連付け
        WarehouseStaff.objects.create(warehouse=warehouse, staff=staff)

    def test_get_top_page_200(self):
        response = self.client.get(reverse("ren:index"))
        self.assertEqual(200, response.status_code)
