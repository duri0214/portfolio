from django.contrib.auth.models import AnonymousUser, User
from django.template.loader import render_to_string
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse

from shopping.models import Product, Store


class TestView(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.create_user(email="tester@b.c", username="John Doe").set_password(
            "12345"
        )
        Store.objects.create(name="笹塚")
        Store.objects.create(name="新宿")
        cls.product = Product.objects.create(
            code="test-product",
            name="テスト商品",
            price=1000,
            description="テスト用の商品です",
            picture="shopping/test-product.jpg",
        )

    def test_get_top_page_200(self):
        """
        シナリオ:
        - 入力: shoppingトップページのURL。
        - 処理: テストクライアントでGETする。
        - 期待値: HTTP 200 が返されること。
        """
        response = self.client.get(reverse("shp:index"))
        self.assertEqual(200, response.status_code)

    def test_payment_confirm_template_requires_login_for_anonymous_user(self):
        """
        シナリオ:
        - 入力: 非ログインユーザーと決済確認テンプレート用の決済情報。
        - 処理: 決済確認テンプレートをレンダリングする。
        - 期待値: ログイン誘導が表示され、Stripe決済フォームは表示されないこと。
        """
        path = reverse("shp:payment_confirm", kwargs={"pk": self.product.pk})
        request = RequestFactory().get(path)
        request.user = AnonymousUser()

        html = render_to_string(
            "shopping/product/payment/confirm.html",
            self._payment_confirm_context(request.user),
            request=request,
        )

        self.assertIn("商品を購入するにはログインが必要です", html)
        self.assertIn(f'{reverse("login")}?next={path}', html)
        self.assertIn(
            reverse("shp:product_detail", kwargs={"pk": self.product.pk}), html
        )
        self.assertNotIn('id="payment-form"', html)
        self.assertNotIn('id="submit-button"', html)

    def test_payment_confirm_template_shows_payment_form_for_authenticated_user(self):
        """
        シナリオ:
        - 入力: ログイン済みユーザーとclient_secretを含む決済確認テンプレート用の決済情報。
        - 処理: 決済確認テンプレートをレンダリングする。
        - 期待値: Stripe決済フォームが表示され、ログイン誘導は表示されないこと。
        """
        user = User.objects.create_user(username="payment-user", password="password")
        path = reverse("shp:payment_confirm", kwargs={"pk": self.product.pk})
        request = RequestFactory().get(path)
        request.user = user

        html = render_to_string(
            "shopping/product/payment/confirm.html",
            self._payment_confirm_context(request.user),
            request=request,
        )

        self.assertIn('id="payment-form"', html)
        self.assertIn('id="submit-button"', html)
        self.assertIn("支払う", html)
        self.assertNotIn("商品を購入するにはログインが必要です", html)

    def _payment_confirm_context(self, user):
        return {
            "object": self.product,
            "user": user,
            "quantity": 2,
            "subtotal": 2000,
            "tax": 200,
            "total_price": 2200,
            "public_key": "pk_test_dummy",
            "client_secret": "pi_dummy_secret_dummy",
        }
