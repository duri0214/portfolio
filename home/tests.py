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
        self.assertContains(response, "Bookmanを開く")
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
            ("about_hospital", "hsp:index", "HOSPITAL"),
            ("about_soil_analysis", "soil:home", "SOIL ANALYSIS"),
            ("about_vietnam_research", "vnm:index", "VIETNAM"),
            ("about_usa_research", "usa:index", "USA"),
            ("about_gmarker", "mrk:index", "GMARKER"),
            ("about_shopping", "shp:index", "SHOPPING"),
            ("about_rental_shop", "ren:index", "RENTAL SHOP"),
            ("about_taxonomy", "txo:index", "TAXONOMY"),
            ("about_securities", "sec:index", "SECURITIES REPORT"),
            ("about_llm_chat", "llm:index", "LLM CHAT"),
            ("about_ai_agent", "agt:index", "AI AGENT"),
            ("about_jp_stocks", "jpn:index", "JP STOCKS"),
            ("about_welfare_services", "welf:index", "WELFARE SERVICES"),
            ("about_kokkai", "kokkai:index", "KOKKAI"),
            ("about_bank", "bank:index", "BANK"),
        )

        for detail_name, app_name, app_label in catalog_links:
            with self.subTest(detail_name=detail_name):
                response = self.client.get(reverse(f"home:{detail_name}"))

                self.assertContains(response, reverse(app_name))
                self.assertContains(response, f"{app_label}を開く")
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

    def test_usa_research_does_not_render_broken_external_gallery(self):
        """
        シナリオ:
        - 入力: USA リサーチの紹介ページを GET する。
        - 処理: 紹介ページの HTML を確認する。
        - 期待値: 画像では表示できない外部 PDF のギャラリーが存在しないこと。
        """
        response = self.client.get(reverse("home:about_usa_research"))

        self.assertNotContains(response, "galleryCarousel")
        self.assertNotContains(response, "www.msci.com/documents")
