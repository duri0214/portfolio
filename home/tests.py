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
        self.assertContains(response, "https://bookman.henojiya.net/")

    def test_bookman_detail_links_to_external_application(self):
        """
        シナリオ:
        - 入力: Bookman の紹介ページを GET する。
        - 処理: Bookman 紹介ページのレスポンスを取得する。
        - 期待値: 公開中の Bookman サブドメインへのリンクが表示されること。
        """
        response = self.client.get(reverse("home:about_bookman"))

        self.assertContains(response, "https://bookman.henojiya.net/")
        self.assertContains(response, "支店別所蔵")
        self.assertContains(response, "貸出・返却と予約・取り置き")

    def test_catalog_details_have_app_open_buttons(self):
        """
        シナリオ:
        - 入力: 各カタログ詳細ページと対応するアプリ URL の組み合わせ。
        - 処理: 各詳細ページを GET する。
        - 期待値: ヘッダーにアプリを開くリンクが表示されること。
        """
        catalog_links = (
            ("about_hospital", "hsp:index"),
            ("about_soil_analysis", "soil:home"),
            ("about_vietnam_research", "vnm:index"),
            ("about_usa_research", "usa:index"),
            ("about_gmarker", "mrk:index"),
            ("about_shopping", "shp:index"),
            ("about_rental_shop", "ren:index"),
            ("about_taxonomy", "txo:index"),
            ("about_securities", "sec:index"),
            ("about_llm_chat", "llm:index"),
            ("about_ai_agent", "agt:index"),
            ("about_jp_stocks", "jpn:index"),
            ("about_welfare_services", "welf:index"),
            ("about_kokkai", "kokkai:index"),
            ("about_bank", "bank:index"),
        )

        for detail_name, app_name in catalog_links:
            with self.subTest(detail_name=detail_name):
                response = self.client.get(reverse(f"home:{detail_name}"))

                self.assertContains(response, reverse(app_name))
                button_href = f'href="{reverse(app_name)}" class="btn btn-primary"'
                self.assertEqual(response.content.decode().count(button_href), 1)

    def test_catalog_app_links_follow_current_host(self):
        """
        シナリオ:
        - 入力: 本番ホストを指定して BANK の紹介ページを GET する。
        - 処理: アプリ起動ボタンの URL をレスポンスから確認する。
        - 期待値: 固定した localhost URL ではなく、現在のホストに解決できる相対 URL が使われること。
        """
        response = self.client.get(
            reverse("home:about_bank"),
            secure=True,
            HTTP_HOST="www.henojiya.net",
        )

        self.assertContains(response, 'href="/bank/"')
        self.assertNotContains(response, "127.0.0.1:8000/bank/")
