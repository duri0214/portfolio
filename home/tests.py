from pathlib import Path

from django.test import SimpleTestCase
from django.urls import reverse

from home.domain.valueobject.catalog import Catalog, DEFAULT_THUMBNAIL


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
        self.assertContains(
            response,
            'href="https://bookman.henojiya.net/" class="btn btn-primary">Bookmanを開く</a>',
        )
        self.assertContains(response, "支店別所蔵")
        self.assertContains(response, "貸出・返却と予約・取り置き")

    def test_catalog_details_have_app_open_buttons(self):
        """
        シナリオ:
        - 入力: 各カタログ詳細ページと対応するアプリ URL の組み合わせ。
        - 処理: 各詳細ページを GET する。
        - 期待値: ヘッダーにアプリを開くリンクが表示されること。
        """
        for catalog in Catalog.all():
            if not catalog.app_url_name:
                continue

            with self.subTest(slug=catalog.slug):
                response = self.client.get(reverse(f"home:{catalog.detail_url_name}"))

                app_url = reverse(catalog.app_url_name)
                self.assertContains(response, app_url)
                self.assertContains(response, f"{catalog.app_label}を開く")
                button_href = f'href="{app_url}" class="btn btn-primary"'
                self.assertEqual(response.content.decode().count(button_href), 1)
                self.assertNotContains(
                    response,
                    f'href="{app_url}" class="btn btn-primary" target="_blank"',
                )

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


class CatalogDefinitionTests(SimpleTestCase):
    def test_catalog_thumbnail_files_are_registered_and_exist(self):
        """
        シナリオ:
        - 入力: カタログ定義と home のサムネイルディレクトリにある PNG ファイル。
        - 処理: 定義上の画像名と実ファイル名を集合として比較する。
        - 期待値: 登録漏れや存在しない画像参照がなく、共有フォールバック画像も存在すること。
        """
        image_directory = Path(__file__).parent / "static" / "home" / "images"
        registered_images = {
            catalog.thumbnail_name for catalog in Catalog.all()
        } | {DEFAULT_THUMBNAIL}
        actual_images = {path.name for path in image_directory.glob("*.png")}

        self.assertEqual(actual_images, registered_images)
        for catalog in Catalog.all():
            if catalog.thumbnail:
                self.assertEqual(catalog.thumbnail, f"{catalog.slug}.png")

    def test_home_and_catalog_details_use_shared_thumbnail_definitions(self):
        """
        シナリオ:
        - 入力: HOME と全カタログ詳細ページのレスポンス。
        - 処理: カタログ定義から解決したサムネイルと alt テキストを確認する。
        - 期待値: HOME と詳細ページが同じサムネイル定義を表示すること。
        """
        home_response = self.client.get(reverse("home:index"))

        for catalog in Catalog.all():
            image_src = f"/static/{catalog.thumbnail_path}"
            with self.subTest(page="home", slug=catalog.slug):
                self.assertContains(home_response, f'src="{image_src}"')
                self.assertContains(home_response, f'alt="{catalog.alt}"')

            detail_response = self.client.get(
                reverse(f"home:{catalog.detail_url_name}")
            )
            with self.subTest(page="detail", slug=catalog.slug):
                self.assertContains(detail_response, f'src="{image_src}"')
                self.assertContains(detail_response, f'alt="{catalog.alt}"')
