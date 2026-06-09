from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

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


class RokunohePdfDownloadViewTest(TestCase):
    def test_superuser_can_start_pdf_download(self):
        """
        シナリオ:
        - 入力: superuserでログインした状態。
        - 処理: 六戸町会議録PDF保存ボタンのPOST先へリクエストする。
        - 期待値: 管理コマンドが呼び出され、トップページへリダイレクトされること。
        """
        user = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password",
        )
        self.client.force_login(user)

        with patch("jp_stocks.views.call_command") as call_command_mock:
            response = self.client.post(reverse("jpn:rokunohe_pdf_download"))

        self.assertEqual(302, response.status_code)
        self.assertEqual(reverse("jpn:index"), response.url)
        call_command_mock.assert_called_once_with("rokunohe_pdf_download")

    def test_non_superuser_cannot_start_pdf_download(self):
        """
        シナリオ:
        - 入力: 一般ユーザーでログインした状態。
        - 処理: 六戸町会議録PDF保存ボタンのPOST先へリクエストする。
        - 期待値: 403が返り、管理コマンドは呼び出されないこと。
        """
        user = User.objects.create_user(
            username="user",
            email="user@example.com",
            password="password",
        )
        self.client.force_login(user)

        with patch("jp_stocks.views.call_command") as call_command_mock:
            response = self.client.post(reverse("jpn:rokunohe_pdf_download"))

        self.assertEqual(403, response.status_code)
        call_command_mock.assert_not_called()

    def test_non_superuser_sees_disabled_pdf_download_button(self):
        """
        シナリオ:
        - 入力: 一般ユーザーでログインした状態。
        - 処理: jp_stocksトップページを表示する。
        - 期待値: 六戸町会議録PDF保存ボタンがdisabledとして表示されること。
        """
        user = User.objects.create_user(
            username="user",
            email="user@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.get(reverse("jpn:index"))

        self.assertContains(response, "六戸町会議録PDF保存")
        self.assertContains(response, "disabled")
