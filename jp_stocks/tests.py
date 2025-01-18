from django.test import TestCase

from jp_stocks.domain.service.order import OrderBookService
from jp_stocks.domain.valueobject.order import OrderPair
from jp_stocks.models import Order


class OrderBookServiceTest(TestCase):
    def setUp(self):
        """
        テスト実行時にデータベースのOrderテーブルを初期化。
        """
        Order.objects.all().delete()

    def test_complete_cancellation(self):
        """
        同価格で売り注文と買い注文が完全に相殺される場合をテスト
        """
        # データを作成
        Order.objects.create(side="sell", price=100, quantity=50)
        Order.objects.create(side="buy", price=100, quantity=50)

        # サービスを実行
        result = OrderBookService.calculate_order_book()

        # 期待結果
        expected_result = [OrderPair(price=100, sell_quantity=0, buy_quantity=0)]
        self.assertEqual(result, expected_result)

    def test_partial_cancellation_sell_remains(self):
        """
        部分的な相殺で売り注文が残る場合をテスト
        """
        # データを作成
        Order.objects.create(side="sell", price=100, quantity=60)
        Order.objects.create(side="buy", price=100, quantity=40)

        # サービスを実行
        result = OrderBookService.calculate_order_book()

        # 期待結果
        expected_result = [OrderPair(price=100, sell_quantity=20, buy_quantity=0)]
        self.assertEqual(result, expected_result)

    def test_partial_cancellation_buy_remains(self):
        """
        部分的な相殺で買い注文が残る場合をテスト
        """
        # データを作成
        Order.objects.create(side="sell", price=100, quantity=30)
        Order.objects.create(side="buy", price=100, quantity=50)

        # サービスを実行
        result = OrderBookService.calculate_order_book()

        # 期待結果
        expected_result = [OrderPair(price=100, sell_quantity=0, buy_quantity=20)]
        self.assertEqual(result, expected_result)

    def test_no_match(self):
        """
        売りと買いの価格帯が異なり、全くマッチしない場合をテスト
        """
        # データを作成
        Order.objects.create(side="sell", price=101, quantity=50)
        Order.objects.create(side="buy", price=100, quantity=30)

        # サービスを実行
        result = OrderBookService.calculate_order_book()

        # 期待結果
        expected_result = [
            OrderPair(price=100, sell_quantity=0, buy_quantity=30),
            OrderPair(price=101, sell_quantity=50, buy_quantity=0),
        ]
        self.assertEqual(result, expected_result)

    def test_multiple_orders(self):
        """
        複数の売り注文と買い注文があり、一部が相殺される場合をテスト
        """
        # データを作成
        Order.objects.create(side="sell", price=100, quantity=50)
        Order.objects.create(side="sell", price=105, quantity=20)
        Order.objects.create(side="buy", price=100, quantity=40)
        Order.objects.create(side="buy", price=105, quantity=10)

        # サービスを実行
        result = OrderBookService.calculate_order_book()

        # 期待結果
        expected_result = [
            OrderPair(price=100, sell_quantity=10, buy_quantity=0),
            OrderPair(price=105, sell_quantity=10, buy_quantity=0),
        ]
        self.assertEqual(result, expected_result)
