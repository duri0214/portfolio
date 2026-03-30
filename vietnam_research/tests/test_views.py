from datetime import datetime, timezone
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from vietnam_research.models import (
    Articles,
    Likes,
    ExchangeRate,
    Symbol,
    Market,
    Watchlist,
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

    def test_watchlist_register_redirects_to_watchlist(self):
        """
        ウォッチリスト登録後、ウォッチリストページにリダイレクトすることを検証
        """
        self.client.login(username=self.user.username, password=self.password_plane)
        market = Market.objects.create(name="HOSE")
        symbol = Symbol.objects.create(
            code="VNM_REG", name="Vina-milk_REG", market=market
        )
        data = {
            "symbol": symbol.id,
            "bought_day": "2024-03-28",
            "stocks_price": 70000,
            "stocks_count": 100,
        }
        response = self.client.post(reverse("vnm:watchlist_create"), data=data)
        self.assertRedirects(response, reverse("vnm:watchlist"))

    def test_watchlist_edit_redirects_to_watchlist(self):
        """
        ウォッチリスト編集後、ウォッチリストページにリダイレクトすることを検証
        """
        self.client.login(username=self.user.username, password=self.password_plane)
        market = Market.objects.create(name="HOSE_EDIT")
        symbol = Symbol.objects.create(code="FPT_EDIT", name="FPT_EDIT", market=market)
        watchlist = Watchlist.objects.create(
            user=self.user,
            symbol=symbol,
            bought_day="2024-03-28",
            stocks_price=90000,
            stocks_count=100,
        )
        data = {
            "symbol": symbol.id,
            "bought_day": "2024-03-29",
            "stocks_price": 95000,
            "stocks_count": 100,
        }
        response = self.client.post(
            reverse("vnm:watchlist_edit", kwargs={"pk": watchlist.pk}), data=data
        )
        self.assertRedirects(response, reverse("vnm:watchlist"))

    def test_watchlist_duplicate_registration_fails(self):
        """
        同じ銘柄を二重に登録できないことを検証
        """
        self.client.login(username=self.user.username, password=self.password_plane)
        market = Market.objects.create(name="HOSE_DUP")
        symbol = Symbol.objects.create(
            code="VNM_DUP", name="Vina-milk_DUP", market=market
        )

        # 1回目の登録
        data = {
            "symbol": symbol.id,
            "bought_day": "2024-03-28",
            "stocks_price": 70000,
            "stocks_count": 100,
        }
        response = self.client.post(reverse("vnm:watchlist_create"), data=data)
        self.assertRedirects(response, reverse("vnm:watchlist"))
        self.assertEqual(
            Watchlist.objects.filter(user=self.user, symbol=symbol).count(), 1
        )

        # 2回目の登録（重複）
        response = self.client.post(reverse("vnm:watchlist_create"), data=data)

        # 重複が許されないため、リダイレクトせずにフォーム再表示（エラーメッセージ付き）になることを検証
        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response, "この銘柄はすでにウォッチリストに登録されています。"
        )

    def test_stock_tools_min_fee_badge(self):
        """
        株式ツールのシミュレーターで最低手数料が適用された場合にバッジが表示されることを検証
        """
        # 1. 最低手数料が適用されるケース (少額)
        # 予算 10,000円, 単価 50,000VND -> 購入口数少
        # 2.2% が 1,320,000VND を下回るような設定
        data = {"budget": 10000, "unit_price": 50000}
        self.client.post(reverse("vnm:tools"), data=data)
        response = self.client.get(reverse("vnm:tools"))
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "最低手数料適用")

        # 2. 最低手数料が適用されないケース (高額)
        # 予算 10,000,000円 -> 約定代金が大きくなり 2.2% > 1,320,000VND になる
        data = {"budget": 10000000, "unit_price": 50000}
        self.client.post(reverse("vnm:tools"), data=data)
        response = self.client.get(reverse("vnm:tools"))
        self.assertEqual(200, response.status_code)
        self.assertNotContains(response, "最低手数料適用")

    def test_watchlist_delete_view(self):
        """
        ウォッチリストの削除機能が正常に動作することを検証
        """
        self.client.login(username=self.user.username, password=self.password_plane)
        market = Market.objects.create(name="HOSE_DEL")
        symbol = Symbol.objects.create(code="FPT_DEL", name="FPT_DEL", market=market)
        watchlist = Watchlist.objects.create(
            user=self.user,
            symbol=symbol,
            bought_day="2024-03-28",
            stocks_price=90000,
            stocks_count=100,
        )

        # 削除確認ページの表示
        response = self.client.get(
            reverse("vnm:watchlist_delete", kwargs={"pk": watchlist.pk})
        )
        self.assertEqual(200, response.status_code)
        self.assertTemplateUsed(
            response, "vietnam_research/watchlist/delete_confirm.html"
        )
        self.assertContains(response, "FPT_DEL")

        # 削除実行
        response = self.client.post(
            reverse("vnm:watchlist_delete", kwargs={"pk": watchlist.pk})
        )
        self.assertRedirects(response, reverse("vnm:watchlist"))
        self.assertFalse(Watchlist.objects.filter(pk=watchlist.pk).exists())

    def test_watchlist_delete_permission(self):
        """
        他人のウォッチリストを削除できないことを検証
        """
        # 他人を作成
        other_user = User.objects.create_user(username="other", password="password")
        market = Market.objects.create(name="HOSE_P")
        symbol = Symbol.objects.create(code="FPT_P", name="FPT_P", market=market)
        watchlist = Watchlist.objects.create(
            user=other_user,
            symbol=symbol,
            bought_day="2024-03-28",
            stocks_price=90000,
            stocks_count=100,
        )

        # 自分としてログイン
        self.client.login(username=self.user.username, password=self.password_plane)

        # 他人のウォッチリスト削除を試みる
        response = self.client.get(
            reverse("vnm:watchlist_delete", kwargs={"pk": watchlist.pk})
        )
        self.assertEqual(404, response.status_code)

        response = self.client.post(
            reverse("vnm:watchlist_delete", kwargs={"pk": watchlist.pk})
        )
        self.assertEqual(404, response.status_code)
        self.assertTrue(Watchlist.objects.filter(pk=watchlist.pk).exists())
