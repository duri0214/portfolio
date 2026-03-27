from django.test import TestCase
from django.urls import reverse

from rental_shop.models import (
    Warehouse,
    Staff,
    WarehouseStaff,
    Item,
    RentalStatus,
    Company,
    BillingPerson,
    BillingStatus,
    Cart,
    CartItem,
)


class TestView(TestCase):
    @classmethod
    def setUpTestData(cls):
        # ステータスマスタを作成
        RentalStatus.objects.create(id=RentalStatus.STOCK, name="在庫")
        RentalStatus.objects.create(id=RentalStatus.RENTAL, name="貸出中")
        RentalStatus.objects.create(id=RentalStatus.CART, name="カート内")

        BillingStatus.objects.create(id=BillingStatus.BILLING, name="請求中")

        # 会社と担当者を作成
        company = Company.objects.create(name="テスト会社", address="テスト住所")
        BillingPerson.objects.create(
            company=company, name="担当者1", email="test@example.com"
        )

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
        staff = Staff.objects.create(
            id=1, name="スタッフ1", created_at="2023-02-12 00:00:00"
        )
        # 倉庫とスタッフを関連付け
        WarehouseStaff.objects.create(warehouse=warehouse, staff=staff)

        # アイテムを作成
        Item.objects.create(
            serial_number="SN001",
            name="アイテム1",
            price=1000,
            pos_x=1,
            pos_y=1,
            pos_z=1,
            rental_status_id=RentalStatus.STOCK,
            staff=staff,
            warehouse=warehouse,
        )

    def test_get_top_page_200(self):
        response = self.client.get(reverse("ren:index"))
        self.assertEqual(200, response.status_code)

    def test_rent_item(self):
        item = Item.objects.get(serial_number="SN001")
        response = self.client.post(
            reverse("ren:rent_item", kwargs={"item_id": item.id})
        )
        self.assertEqual(302, response.status_code)

        item.refresh_from_db()
        self.assertEqual(RentalStatus.CART, item.rental_status_id)

        # カートが作成されていることを確認
        self.assertTrue(
            Cart.objects.filter(staff_id=1, warehouse=item.warehouse).exists()
        )
        self.assertTrue(CartItem.objects.filter(item=item).exists())

    def test_reset_rentals(self):
        item = Item.objects.get(serial_number="SN001")
        item.rental_status_id = RentalStatus.CART
        item.save()

        response = self.client.post(
            reverse("ren:reset_items", kwargs={"warehouse_id": item.warehouse_id})
        )
        self.assertEqual(302, response.status_code)

        item.refresh_from_db()
        self.assertEqual(RentalStatus.STOCK, item.rental_status_id)
        self.assertFalse(CartItem.objects.filter(item=item).exists())

    def test_invoice_create_updates_items(self):
        item = Item.objects.get(serial_number="SN001")
        staff = Staff.objects.get(pk=1)
        cart = Cart.objects.create(staff=staff, warehouse=item.warehouse)
        CartItem.objects.create(cart=cart, item=item)
        item.rental_status_id = RentalStatus.CART
        item.save()

        company = Company.objects.first()
        person = BillingPerson.objects.first()

        data = {
            "company": company.id,
            "billing_person": person.id,
            "rental_start_date": "2023-01-01",
            "rental_end_date": "2023-01-31",
            "billing_status": BillingStatus.BILLING,
            "staff": staff.id,
        }

        response = self.client.post(reverse("ren:invoice_create"), data=data)
        self.assertEqual(302, response.status_code)

        item.refresh_from_db()
        self.assertEqual(RentalStatus.RENTAL, item.rental_status_id)
        self.assertIsNotNone(item.invoice)
        self.assertFalse(CartItem.objects.filter(item=item).exists())
