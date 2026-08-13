from django.test import SimpleTestCase
from django.urls import reverse


class BookmanHomeTests(SimpleTestCase):
    def test_home_catalog_links_to_bookman_detail(self):
        """
        シナリオ:
        - 入力: HOME のカタログページを GET する。
        - 処理: HOME のレスポンスを取得する。
        - 期待値: Bookman の紹介導線が表示されること。
        """
        response = self.client.get(reverse("home:index"))

        self.assertContains(response, "図書館業務システム Bookman")
        self.assertContains(response, reverse("home:about_bookman"))

    def test_bookman_detail_links_to_external_application(self):
        """
        シナリオ:
        - 入力: Bookman の紹介ページを GET する。
        - 処理: Bookman 紹介ページのレスポンスを取得する。
        - 期待値: 公開中の Bookman サブドメインへのリンクが表示されること。
        """
        response = self.client.get(reverse("home:about_bookman"))

        self.assertContains(response, "https://bookman.henojiya.net/")
