from datetime import datetime, timezone
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from vietnam_research.models import (
    Articles,
    Likes,
    ExchangeRate,
    FinancialResultWatch,
    Symbol,
    Market,
    Unit,
)


class TestView(TestCase):
    def setUp(self):
        # Patch external RSS access so tests never hit the network
        self._rss_patcher = patch(
            "vietnam_research.domain.service.market.MarketRetrievalService.rss_feed",
            return_value={
                "entries": [],
                "feed": {
                    "updated": datetime.now(timezone.utc).strftime(
                        "%Y/%m/%d %H:%M:%S %z"
                    )
                },
            },
        )
        self._rss_patcher.start()

        self.password_plane = "<PASSWORD>"
        self.user = User.objects.create_user(
            id=1, username="john_doe", email="user@example.com"
        )
        self.user.set_password(self.password_plane)
        self.user.save()
        self.article = Articles.objects.create(
            id=1, title="Hello", note="How are you", user=self.user
        )

        ExchangeRate.objects.create(
            base_cur_code="JPY",
            dest_cur_code="VND",
            rate=170.55,
        )

        # セッションデータに予算と単価を設定
        session = self.client.session
        session["budget"] = 10000  # Or some sensible default
        session["unit_price"] = 5000  # Or some sensible default
        session.save()

    def tearDown(self):
        # stop patchers
        self._rss_patcher.stop()

    def test_show_index_page_without_budget_and_unit_price(self):
        """
        セッションに予算と単価が設定されていない場合でも、indexページが正常に表示される
        """
        # セッションから予算と単価を削除
        session = self.client.session
        del session["budget"]
        del session["unit_price"]
        session.save()

        # ログインしていない場合
        response = self.client.get(reverse("vnm:index"))
        self.assertEqual(200, response.status_code)

        # ログインしている場合
        logged_in = self.client.login(
            username=self.user.username, password=self.password_plane
        )
        self.assertTrue(logged_in)

        response = self.client.get(reverse("vnm:index"))
        self.assertEqual(200, response.status_code)
        self.assertContains(
            response, f'<i class="fas fa-user"></i> {self.user.username}さん', html=True
        )

        # ログアウト後
        self.client.logout()
        response = self.client.get(reverse("vnm:index"))
        self.assertEqual(200, response.status_code)

    def test_redirect_to_login_page(self):
        """
        ログインしていない場合、保護された記事作成ページに遷移しようとするとログインページにリダイレクトする
        """
        response = self.client.get(reverse("vnm:article_create"))
        self.assertRedirects(
            response, "/accounts/login/?next=/vietnam_research/article/create/"
        )

    def test_can_navigate_to_article_create_page(self):
        """
        ログインしている場合、保護されている記事作成ページに遷移できる
        """
        logged_in = self.client.login(
            username=self.user.username, password=self.password_plane
        )
        self.assertTrue(logged_in)
        response = self.client.get(reverse("vnm:article_create"))
        self.assertTemplateUsed(response, "vietnam_research/articles/create.html")

    def test_can_create_likes(self):
        logged_in = self.client.login(
            username=self.user.username, password=self.password_plane
        )
        self.assertTrue(logged_in)

        # create 3 users
        usernames = ["user1", "user2", "user3"]
        [
            User.objects.create_user(username=x).set_password(self.password_plane)
            for x in usernames
        ]

        # already got 'likes' from 3 users
        [
            Likes.objects.create(
                articles=self.article, user=User.objects.get(username=x)
            )
            for x in usernames
        ]
        self.assertEqual(3, Likes.objects.filter(articles=self.article).count())

        # post 'likes' then the count should be 4
        response = self.client.post(
            reverse("vnm:likes", kwargs={"article_id": self.article.pk})
        )
        self.assertEqual(200, response.status_code)
        self.assertEqual(4, Likes.objects.filter(articles=self.article).count())

    def test_can_not_create_likes_because_the_article_not_exist(self):
        logged_in = self.client.login(
            username=self.user.username, password=self.password_plane
        )
        self.assertTrue(logged_in)

        # 存在しない記事IDを指定してPOSTリクエストを送信
        response = self.client.post(reverse("vnm:likes", kwargs={"article_id": 999}))

        # 例外が発生し、エラーとなることを確認
        self.assertEqual(400, response.status_code)
        self.assertIn(
            "存在しない記事へのリクエストがありました", response.content.decode("utf-8")
        )

    def test_cannot_create_likes_without_login(self):
        """
        ログインしていない場合、いいね！リクエストは 401 を返す
        """
        self.client.logout()
        response = self.client.post(
            reverse("vnm:likes", kwargs={"article_id": self.article.pk})
        )
        self.assertEqual(401, response.status_code)
        self.assertJSONEqual(response.content, {"error": "login_required"})

    def test_financial_results_create_view_get(self):
        """
        ログインしている場合、決算データ登録ページが表示される
        """
        import datetime

        self.client.login(username=self.user.username, password=self.password_plane)
        response = self.client.get(reverse("vnm:financial_results_create"))
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed(
            response, "vietnam_research/financial_results/create.html"
        )
        # 初期値が今日であることを検証
        form = response.context["form"]
        self.assertEqual(form.fields["recorded_date"].initial, datetime.date.today())
        # 数値フィールドの初期値がない（Noneである）ことを検証
        self.assertIsNone(form.fields["eps_estimate"].initial)
        self.assertIsNone(form.fields["eps_actual"].initial)
        self.assertIsNone(form.fields["sales_estimate"].initial)
        self.assertIsNone(form.fields["sales_actual"].initial)
        self.assertIsNone(form.fields["y_over_y_growth_rate"].initial)

    def test_watchlist_create_view_get(self):
        """
        ログインしている場合、ウォッチリスト登録ページが表示される
        """
        import datetime

        self.client.login(username=self.user.username, password=self.password_plane)
        response = self.client.get(reverse("vnm:watchlist_create"))
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed(response, "vietnam_research/watchlist/create.html")
        # 初期値が今日であることを検証
        form = response.context["form"]
        self.assertEqual(form.fields["bought_day"].initial, datetime.date.today())

    def test_financial_results_create_view_post(self):
        """
        ログインしている場合、決算データが正常に登録できる
        """
        from vietnam_research.models import Unit, Symbol, FinancialResultWatch, Market

        self.client.login(username=self.user.username, password=self.password_plane)
        market = Market.objects.create(name="HOSE")
        unit = Unit.objects.create(name="10億VND")
        symbol = Symbol.objects.create(
            code="FPT", name="FPT Corporation", market=market
        )

        data = {
            "recorded_date": "2024-03-28",
            "symbol": symbol.pk,
            "quarter": 1,
            "eps_ok": True,
            "sales_ok": True,
            "guidance_ok": True,
            "eps_unit": unit.pk,
            "eps_estimate": 1000.0,
            "eps_actual": 1100.0,
            "sales_unit": unit.pk,
            "sales_estimate": 5000.0,
            "sales_actual": 5500.0,
            "y_over_y_growth_rate": 20.0,
            "note_url": "https://example.com",
        }
        response = self.client.post(reverse("vnm:financial_results_create"), data)
        self.assertEqual(302, response.status_code)
        self.assertTrue(FinancialResultWatch.objects.filter(symbol=symbol).exists())

    def test_financial_results_create_view_post_without_note_url(self):
        """
        note_url が空でも決算データが正常に登録できる
        """
        from vietnam_research.models import Unit, Symbol, FinancialResultWatch, Market

        self.client.login(username=self.user.username, password=self.password_plane)
        market = Market.objects.create(name="HOSE")
        unit = Unit.objects.create(name="10億VND")
        symbol = Symbol.objects.create(
            code="FPT", name="FPT Corporation", market=market
        )

        data = {
            "recorded_date": "2024-03-28",
            "symbol": symbol.pk,
            "quarter": 1,
            "eps_ok": True,
            "sales_ok": True,
            "guidance_ok": True,
            "eps_unit": unit.pk,
            "eps_estimate": 1000.0,
            "eps_actual": 1100.0,
            "sales_unit": unit.pk,
            "sales_estimate": 5000.0,
            "sales_actual": 5500.0,
            "y_over_y_growth_rate": 20.0,
            "note_url": "",  # 空
        }
        response = self.client.post(reverse("vnm:financial_results_create"), data)
        self.assertEqual(302, response.status_code)
        self.assertTrue(
            FinancialResultWatch.objects.filter(symbol=symbol, note_url="").exists()
            or FinancialResultWatch.objects.filter(
                symbol=symbol, note_url=None
            ).exists()
        )

    def test_financial_results_create_view_post_invalid_quarter(self):
        """
        1-4 以外の不正な四半期値を送信した場合、バリデーションエラーとなる
        """
        from vietnam_research.models import Unit, Symbol, Market

        self.client.login(username=self.user.username, password=self.password_plane)
        market = Market.objects.create(name="HOSE")
        unit = Unit.objects.create(name="10億VND")
        symbol = Symbol.objects.create(
            code="FPT", name="FPT Corporation", market=market
        )

        data = {
            "recorded_date": "2024-03-28",
            "symbol": symbol.pk,
            "quarter": 5,  # 不正な値
            "eps_ok": True,
            "sales_ok": True,
            "guidance_ok": True,
            "eps_unit": unit.pk,
            "eps_estimate": 1000.0,
            "eps_actual": 1100.0,
            "sales_unit": unit.pk,
            "sales_estimate": 5000.0,
            "sales_actual": 5500.0,
            "y_over_y_growth_rate": 20.0,
            "note_url": "https://example.com",
        }
        response = self.client.post(reverse("vnm:financial_results_create"), data)
        self.assertEqual(200, response.status_code)
        form = response.context["form"]
        self.assertIn("quarter", form.errors)

    def test_financial_results_create_view_post_negative_values(self):
        """
        EPS予想、EPS実績、売上予想、売上実績に負の値を送信した場合、バリデーションエラーとなる
        """
        self.client.login(username=self.user.username, password=self.password_plane)
        market = Market.objects.create(name="HOSE_NEG")
        unit = Unit.objects.create(name="10億VND")
        symbol = Symbol.objects.create(
            code="FPT_NEG", name="FPT Corporation", market=market
        )

        # 数値フィールドに負の値を設定
        data = {
            "recorded_date": "2024-03-28",
            "symbol": symbol.pk,
            "quarter": 1,
            "eps_ok": True,
            "sales_ok": True,
            "guidance_ok": True,
            "eps_unit": unit.pk,
            "eps_estimate": -100.0,
            "eps_actual": -100.0,
            "sales_unit": unit.pk,
            "sales_estimate": -1000.0,
            "sales_actual": -1000.0,
            "y_over_y_growth_rate": 20.0,
            "note_url": "https://example.com",
        }
        response = self.client.post(reverse("vnm:financial_results_create"), data)
        self.assertEqual(200, response.status_code)
        form = response.context["form"]

        self.assertIn("eps_estimate", form.errors)
        self.assertIn("eps_actual", form.errors)
        self.assertIn("sales_estimate", form.errors)
        self.assertIn("sales_actual", form.errors)

    def test_financial_results_detail_view_display_quarter_with_q(self):
        """決算詳細画面で四半期が 'Q' つきで表示されることを確認"""
        # マスタデータの準備
        market = Market.objects.create(
            code="HOSE_DET", name="ホーチミン証券取引所詳細用"
        )
        symbol = Symbol.objects.create(
            code="DETAIL_VNM", name="Vinamilk_DET", market=market
        )
        unit = Unit.objects.create(name="10億VND")

        # 決算データの作成
        FinancialResultWatch.objects.create(
            recorded_date=datetime.now().date(),
            symbol=symbol,
            quarter=3,
            eps_ok=True,
            sales_ok=True,
            guidance_ok=True,
            eps_estimate=1000,
            eps_actual=1100,
            sales_estimate=50000,
            sales_actual=55000,
            y_over_y_growth_rate=10.5,
            eps_unit=unit,
            sales_unit=unit,
        )

        response = self.client.get(
            reverse("vnm:financial_results_detail", kwargs={"ticker": "DETAIL_VNM"})
        )
        self.assertEqual(200, response.status_code)
        # '3Q' が含まれていることを確認
        self.assertContains(response, "3Q")
        # エラーメッセージの内容は環境によって微妙に異なる可能性があるため、キーの存在確認を優先
