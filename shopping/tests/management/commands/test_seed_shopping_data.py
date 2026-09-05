from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from shopping.models import Product, Store, UserAttribute


class SeedShoppingDataCommandTest(TestCase):
    def test_command_creates_data_for_shopping_screen(self):
        """
        シナリオ:
        - 入力: Shopping画面用の初期データが空のDB状態。
        - 処理: Shopping初期データ投入コマンドを実行する。
        - 期待値: 店舗、店員、顧客、商品が作成されること。
        """
        call_command("seed_shopping_data", verbosity=0)

        self.assertEqual(Store.objects.count(), 2)
        self.assertEqual(Product.objects.count(), 3)
        self.assertEqual(
            UserAttribute.objects.filter(role=UserAttribute.Role.STAFF).count(), 1
        )
        self.assertEqual(
            UserAttribute.objects.filter(role=UserAttribute.Role.CUSTOMER).count(), 1
        )
        self.assertTrue(
            get_user_model().objects.filter(username="ピザ焼き太郎").exists()
        )
        self.assertTrue(Product.objects.filter(code="margherita").exists())

    def test_command_is_idempotent(self):
        """
        シナリオ:
        - 入力: Shopping初期データを一度投入済みのDB状態。
        - 処理: 同じ初期データ投入コマンドを再実行する。
        - 期待値: 店舗、ユーザー属性、商品が重複作成されないこと。
        """
        call_command("seed_shopping_data", verbosity=0)
        counts = {
            "stores": Store.objects.count(),
            "users": get_user_model().objects.count(),
            "profiles": UserAttribute.objects.count(),
            "products": Product.objects.count(),
        }

        call_command("seed_shopping_data", verbosity=0)

        self.assertEqual(counts["stores"], Store.objects.count())
        self.assertEqual(counts["users"], get_user_model().objects.count())
        self.assertEqual(counts["profiles"], UserAttribute.objects.count())
        self.assertEqual(counts["products"], Product.objects.count())
