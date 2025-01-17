from unittest.mock import MagicMock

from django.test import TestCase

from jp_stocks.domain.repository.order import OrderRepository
from jp_stocks.domain.service.order import OrderBookService
from jp_stocks.domain.valueobject.order import OrderSummary
from jp_stocks.models import Order


class OrderRepositoryTest(TestCase):
    def setUp(self):
        """
        売り注文と買い注文のテストデータを準備。
        """
        # 既存のデータを削除してリセット
        Order.objects.all().delete()

        # 売り注文データ
        Order.objects.create(
            side="sell", price=100, quantity=300, fulfilled_quantity=200, status="open"
        )  # 残量100 (有効)
        Order.objects.create(
            side="sell", price=101, quantity=100, fulfilled_quantity=0, status="open"
        )  # 残量100 (有効)
        Order.objects.create(
            side="sell", price=103, quantity=50, fulfilled_quantity=0, status="open"
        )  # 残量50 (有効)
        Order.objects.create(
            side="sell",
            price=104,
            quantity=100,
            fulfilled_quantity=100,
            status="fulfilled",
        )  # 満たされた注文（無効）

        # 買い注文データ
        Order.objects.create(
            side="buy", price=102, quantity=150, fulfilled_quantity=0, status="open"
        )  # 残量150 (有効)
        Order.objects.create(
            side="buy", price=101, quantity=150, fulfilled_quantity=50, status="open"
        )  # 残量100 (有効)
        Order.objects.create(
            side="buy",
            price=99,
            quantity=200,
            fulfilled_quantity=200,
            status="fulfilled",
        )  # 満たされた注文（無効）

    def test_get_sell_orders(self):
        """
        売り注文が正しく集計され、「安い順」にソートされることを確認。
        """
        sell_orders = OrderRepository.get_sell_orders()

        # 売り注文の数が正しいことを確認
        self.assertEqual(len(sell_orders), 3)  # 残量がある3件のみ

        # price=100 の注文
        self.assertEqual(sell_orders[0].price, 100)
        self.assertEqual(sell_orders[0].total_quantity, 100)

        # price=101 の注文
        self.assertEqual(sell_orders[1].price, 101)
        self.assertEqual(sell_orders[1].total_quantity, 100)

        # price=103 の注文
        self.assertEqual(sell_orders[2].price, 103)
        self.assertEqual(sell_orders[2].total_quantity, 50)

    def test_get_buy_orders(self):
        """
        買い注文が正しく集計され、「高い順」にソートされることを確認。
        """
        buy_orders = OrderRepository.get_buy_orders()

        # 買い注文の数が正しいことを確認
        self.assertEqual(len(buy_orders), 2)  # 残量がある2件のみ

        # price=102 の注文
        self.assertEqual(buy_orders[0].price, 102)
        self.assertEqual(buy_orders[0].total_quantity, 150)

        # price=101 の注文
        self.assertEqual(buy_orders[1].price, 101)
        self.assertEqual(buy_orders[1].total_quantity, 100)

    def test_no_fulfilled_orders_in_results(self):
        """
        完全に満たされた注文（fulfilled）は結果に含まれないことを確認。
        """
        sell_orders = OrderRepository.get_sell_orders()
        buy_orders = OrderRepository.get_buy_orders()

        # fulfilled の注文が含まれないことを確認
        for order in sell_orders + buy_orders:
            with self.subTest(order=order):
                self.assertNotEqual(order.total_quantity, 0)  # 残量が0でない
                self.assertNotEqual(order.status, "fulfilled")  # fulfilledでない


class OrderBookServiceTest(TestCase):
    def test_get_order_book(self):
        mock_repository = MagicMock()
        mock_repository.get_sell_orders.return_value = [
            OrderSummary(price=100, total_quantity=50, status="open")
        ]
        mock_repository.get_buy_orders.return_value = [
            OrderSummary(price=200, total_quantity=30, status="open")
        ]

        service = OrderBookService(repository=mock_repository)
        combined_orders = service.get_order_book()

        # OrderPair のプロパティを使って確認
        self.assertEqual(len(combined_orders), 1)

        # 売り注文の確認
        self.assertEqual(combined_orders[0].sell_order.price, 100)
        self.assertEqual(combined_orders[0].sell_order.total_quantity, 50)

        # 買い注文の確認
        self.assertEqual(combined_orders[0].buy_order.price, 200)
        self.assertEqual(combined_orders[0].buy_order.total_quantity, 30)
