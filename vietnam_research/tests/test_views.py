from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from vietnam_research.models import Articles, Likes, ExchangeRate


class TestView(TestCase):
    def setUp(self):
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
