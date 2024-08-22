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

    def test_show_index_page(self):
        """
        ログインしていない場合、indexページに遷移すると `ゲストさん` が表示される
        ログインしている場合、indexページに遷移すると `<email>さん`　が表示される
        ログアウトして、indexページに遷移すると `ゲストさん` が表示される
        """
        response = self.client.get(reverse("vnm:index"))
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "ゲストさん", html=True)

        logged_in = self.client.login(
            username=self.user.username, password=self.password_plane
        )
        self.assertTrue(logged_in)

        response = self.client.get(reverse("vnm:index"))
        self.assertEqual(200, response.status_code)
        self.assertContains(response, f"{self.user.username}さん", html=True)

        self.client.logout()
        response = self.client.get(reverse("vnm:index"))
        self.assertEqual(200, response.status_code)
        self.assertContains(response, "ゲストさん", html=True)

    def test_redirect_to_login_page(self):
        """
        ログインしていない場合、保護された記事作成ページに遷移しようとするとログインページにリダイレクトする
        """
        response = self.client.get(reverse("vnm:article_create"))
        self.assertRedirects(response, "/accounts/login/?next=/article/create/")

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
