from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
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

    def test_superuser_redirects_when_pdf_download_is_already_running(self):
        """
        シナリオ:
        - 入力: superuserでログインし、PDF保存処理が既に実行中の状態。
        - 処理: 六戸町会議録PDF保存ボタンのPOST先へリクエストする。
        - 期待値: 例外で500にせず、トップページへリダイレクトされること。
        """
        user = User.objects.create_superuser(
            username="admin2",
            email="admin2@example.com",
            password="password",
        )
        self.client.force_login(user)

        with patch(
            "jp_stocks.views.call_command",
            side_effect=CommandError("六戸町PDFダウンロードは既に実行中です。"),
        ):
            response = self.client.post(reverse("jpn:rokunohe_pdf_download"))

        self.assertEqual(302, response.status_code)
        self.assertEqual(reverse("jpn:index"), response.url)

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


class RokunohePdfDownloadCommandTest(TestCase):
    def test_waits_between_external_requests(self):
        """
        シナリオ:
        - 入力: PDFリンクを2件含むHTMLレスポンスと、リクエスト間隔0.1秒。
        - 処理: 六戸町会議録PDFダウンロードコマンドを実行する。
        - 期待値: 2件目以降の外部リクエスト前に待機処理が呼び出されること。
        """
        first_page_response = self._create_response(
            '<a href="file1.pdf">会議録1 [PDF]</a><a href="file2.pdf">会議録2 [PDF]</a>'
        )
        pdf_response = self._create_response("", content=b"%PDF")
        second_page_response = self._create_response("")

        with TemporaryDirectory() as temp_dir:
            with patch(
                "jp_stocks.management.commands.rokunohe_pdf_download.requests.get",
                side_effect=[
                    first_page_response,
                    pdf_response,
                    pdf_response,
                    second_page_response,
                ],
            ), patch(
                "jp_stocks.management.commands.rokunohe_pdf_download.time.sleep"
            ) as sleep_mock, self.assertLogs(
                "jp_stocks.management.commands.rokunohe_pdf_download",
                level="INFO",
            ) as logs:
                call_command("rokunohe_pdf_download", save_dir=temp_dir, delay=0.1)

        self.assertGreaterEqual(sleep_mock.call_count, 2)
        sleep_mock.assert_any_call(0.1)
        self.assertIn("進捗 1/2: ダウンロード中", "\n".join(logs.output))
        self.assertIn("進捗 2/2: ダウンロード中", "\n".join(logs.output))

    def test_skips_existing_pdf_file(self):
        """
        シナリオ:
        - 入力: 保存済みPDFと同じファイル名になるPDFリンクを含むHTMLレスポンス。
        - 処理: 六戸町会議録PDFダウンロードコマンドを実行する。
        - 期待値: 保存済みPDFは再ダウンロードされず、HTML取得のみ実行されること。
        """
        first_page_response = self._create_response(
            '<a href="exists.pdf">保存済み [PDF]</a>'
        )
        second_page_response = self._create_response("")

        with TemporaryDirectory() as temp_dir:
            existing_pdf_path = Path(temp_dir) / "保存済み.pdf"
            existing_pdf_path.write_bytes(b"%PDF")

            with patch(
                "jp_stocks.management.commands.rokunohe_pdf_download.requests.get",
                side_effect=[first_page_response, second_page_response],
            ) as get_mock:
                call_command("rokunohe_pdf_download", save_dir=temp_dir, delay=0)

        self.assertEqual(2, get_mock.call_count)

    def test_rejects_parallel_execution_with_lock_file(self):
        """
        シナリオ:
        - 入力: 保存先に実行中を示すロックファイルが存在する状態。
        - 処理: 六戸町会議録PDFダウンロードコマンドを実行する。
        - 期待値: CommandErrorが発生し、並行実行が拒否されること。
        """
        with TemporaryDirectory() as temp_dir:
            lock_path = Path(temp_dir) / ".rokunohe_pdf_download.lock"
            lock_path.write_text("running", encoding="utf-8")

            with self.assertRaises(CommandError):
                call_command("rokunohe_pdf_download", save_dir=temp_dir, delay=0)

    def _create_response(self, text: str, content: bytes = b"") -> Mock:
        response = Mock()
        response.text = text
        response.content = content
        response.apparent_encoding = "utf-8"
        response.raise_for_status = Mock()
        return response
