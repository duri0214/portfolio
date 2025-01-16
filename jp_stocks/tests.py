from unittest.mock import MagicMock

from django.test import TestCase

from jp_stocks.domain.repository.order import OrderRepository
from jp_stocks.domain.service.order import OrderBookService
from jp_stocks.domain.valueobject.order import OrderSummary
from jp_stocks.models import Order


class OrderRepositoryTest(TestCase):
    def setUp(self):
        # テストデータ作成
        Order.objects.create(side="sell", price=100, quantity=50, status="open")
        Order.objects.create(side="sell", price=200, quantity=100, status="open")
        Order.objects.create(side="buy", price=150, quantity=40, status="open")

    def test_get_sell_orders(self):
        sell_orders = OrderRepository.get_sell_orders()
        self.assertEqual(len(sell_orders), 2)
        self.assertEqual(sell_orders[0].price, 100)
        self.assertEqual(sell_orders[0].total_quantity, 50)

    def test_get_buy_orders(self):
        buy_orders = OrderRepository.get_buy_orders()
        self.assertEqual(len(buy_orders), 1)
        self.assertEqual(buy_orders[0].price, 150)
        self.assertEqual(buy_orders[0].total_quantity, 40)


class OrderBookServiceTest(TestCase):
    def test_get_order_book(self):
        mock_repository = MagicMock()
        mock_repository.get_sell_orders.return_value = [
            OrderSummary(price=100, total_quantity=50)
        ]
        mock_repository.get_buy_orders.return_value = [
            OrderSummary(price=200, total_quantity=30)
        ]

        service = OrderBookService(repository=mock_repository)
        combined_orders = service.get_order_book()

        self.assertEqual(len(combined_orders), 1)
        self.assertEqual(combined_orders[0][0].price, 100)  # 売り注文
        self.assertEqual(combined_orders[0][1].price, 200)  # 買い注文
