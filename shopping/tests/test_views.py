from django.contrib.auth.models import AnonymousUser, User
from django.template.loader import render_to_string
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse
from django.utils import timezone

from gmarker.models import Place, PlaceReview
from shopping.models import (
    Product,
    Store,
    StorePlanningDataSourceSnapshot,
    StorePlanningTargetStore,
)


class TestView(TestCase):
    @classmethod
    def setUpTestData(cls):
        User.objects.create_user(email="tester@b.c", username="John Doe").set_password(
            "12345"
        )
        cls.superuser = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password",
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

    def setUp(self):
        self.client.force_login(self.superuser)

    def test_get_top_page_200(self):
        """
        シナリオ:
        - 入力: shoppingトップページのURL。
        - 処理: テストクライアントでGETする。
        - 期待値: HTTP 200 が返されること。
        """
        response = self.client.get(reverse("shp:index"))
        self.assertEqual(200, response.status_code)

    def test_top_page_links_to_store_planning(self):
        """
        シナリオ:
        - 入力: shoppingトップページのURL。
        - 処理: テストクライアントでGETする。
        - 期待値: 出店計画画面への導線が表示されること。
        """
        response = self.client.get(reverse("shp:index"))

        self.assertContains(response, "出店計画")
        self.assertContains(response, reverse("shp:store_planning"))

    def test_get_store_planning_page_200(self):
        """
        シナリオ:
        - 入力: e-Stat人口CSVの集計結果が保存済みのDBと、出店計画画面のURL。
        - 処理: テストクライアントでGETする。
        - 期待値: HTTP 200 が返され、評判分析とe-Stat人口分析が表示されること。
        """
        StorePlanningDataSourceSnapshot.objects.create(
            source_key="estat_population_age_groups_13121_073002",
            display_name="e-Stat 国勢調査 年齢別人口",
            source_url="https://www.e-stat.go.jp/stat-search/files",
            status="取得済み: Chapter Table 周辺町丁の年齢別人口",
            data_period="令和2年国勢調査 小地域集計",
            source_updated_at=timezone.now(),
            raw_data={
                "stat_inf_id": "000032163275",
                "resource_id": "000009048041",
                "table_name": "第3表 男女，年齢（5歳階級）別人口，平均年齢及び総年齢－町丁・字等",
                "last_modified_date": "2022-02-10",
                "target_area_name": "東京都足立区東保木間二丁目",
                "prefecture_name": "東京都",
                "city_name": "足立区",
                "city_code": "13121",
                "town_code": "073002",
                "area_hierarchy_level": "4",
                "total_population": 2289,
                "male_population": 1120,
                "female_population": 1169,
                "average_age": 43.8,
                "age_groups": [
                    {
                        "label": "0代",
                        "population": 220,
                        "male_population": 110,
                        "female_population": 110,
                    },
                    {
                        "label": "10代",
                        "population": 220,
                        "male_population": 112,
                        "female_population": 108,
                    },
                ],
            },
        )
        StorePlanningDataSourceSnapshot.objects.create(
            source_key="estat_population_age_groups_13121",
            display_name="e-Stat 国勢調査 年齢別人口: 東京都足立区",
            source_url="https://www.e-stat.go.jp/stat-search/files",
            status="取得済み: 東京都足立区 の年齢別人口",
            data_period="令和2年国勢調査 小地域集計",
            source_updated_at=timezone.now(),
            raw_data={
                "target_area_name": "東京都足立区",
                "prefecture_name": "東京都",
                "city_name": "足立区",
                "city_code": "13121",
                "area_hierarchy_level": "1",
                "age_groups": [],
            },
        )
        response = self.client.get(reverse("shp:store_planning"))

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Chapter Table")
        self.assertContains(response, "OKEI TAPROOM オケタプ")
        self.assertContains(response, "札幌市時計台")
        self.assertContains(response, "データなし表示点検用サンプル")
        self.assertContains(response, 'id="store-planning-store-select"')
        self.assertContains(response, reverse("shp:store_planning_store_create"))
        self.assertContains(
            response,
            "https://www.google.com/maps?q=35.792822,139.8143238",
        )
        self.assertContains(response, "人口集計地域")
        self.assertContains(response, "東京都足立区東保木間二丁目")
        self.assertContains(response, "Google Maps レビュー")
        self.assertContains(response, "半径 500m")
        self.assertContains(response, "e-Stat 年代別人口")
        html = response.content.decode()
        self.assertLess(
            html.index("e-Stat 年代別人口"), html.index("Google Maps レビュー")
        )
        self.assertNotContains(response, "#803")
        self.assertContains(response, "使用した指標")
        self.assertContains(response, "ファイルID")
        self.assertContains(response, "取得条件")
        self.assertContains(response, "2,289人")
        self.assertContains(response, "平均年齢 43.8 歳")
        self.assertContains(response, "男 1,120人")
        self.assertContains(response, "女 1,169人")
        self.assertContains(response, "0代")
        self.assertContains(response, "220人")
        self.assertContains(response, "男女構成")
        self.assertContains(response, "人口の山")
        self.assertContains(response, "人口ボリューム")
        self.assertContains(response, "最大年代比 100.0%")
        self.assertContains(response, "男性比")
        self.assertContains(response, "女性比")
        self.assertContains(response, "男 50.9% / 女 49.1%")
        self.assertContains(response, 'aria-label="人口ボリューム 100.0%"')
        self.assertContains(response, 'aria-label="男性 50.9%"')
        self.assertContains(response, "background-color: #8fb9dd;")
        self.assertContains(response, "background-color: #e6a6b7;")
        self.assertContains(response, "town=073002")
        self.assertContains(response, "resource 000009048041")
        self.assertContains(response, "stat_infid=000032163275")
        self.assertContains(response, "e-Stat CSV カバー範囲")
        self.assertContains(response, "東京都")
        self.assertContains(response, "1 市区町村")
        self.assertContains(response, "レベル1")
        self.assertContains(response, "市区町村単位")
        self.assertContains(response, "レベル4")
        self.assertContains(response, "1件")
        self.assertContains(response, "東京都 足立区")
        self.assertContains(response, "周辺地域比較")
        self.assertContains(response, "地域マップ")
        self.assertContains(response, "開発Tips")
        self.assertContains(response, "Google Maps iframe")
        self.assertContains(response, "Maps JavaScript API")
        self.assertContains(response, "<iframe")
        self.assertContains(response, 'id="store-planning-area-map"')
        self.assertContains(response, "store-planning-map-button")
        self.assertContains(response, "data-map-url=")
        self.assertContains(response, "output=embed")
        self.assertContains(response, "比較対象")
        self.assertContains(response, "対象地域")
        self.assertNotContains(response, "年代構成")
        self.assertContains(response, "地域を開く")
        self.assertContains(response, "代表地点")
        self.assertContains(response, "maps/search/?api=1")
        self.assertContains(
            response,
            "https://www.google.com/maps?q=%E6%9D%B1%E4%BA%AC%E9%83%BD%E8%B6%B3%E7%AB%8B%E5%8C%BA%E6%9D%B1%E4%BF%9D%E6%9C%A8%E9%96%93%E4%BA%8C%E4%B8%81%E7%9B%AE&amp;output=embed",
        )
        self.assertNotContains(
            response,
            'data-map-url="https://www.google.com/maps?q=35.792822,139.8143238',
        )
        self.assertNotContains(response, "店舗ピン")
        self.assertContains(response, "store-planning-map-button btn-primary")
        self.assertContains(response, 'role="progressbar"')
        self.assertNotContains(response, "店前通行量シナリオ")
        self.assertNotContains(response, "立地リスク判定")
        self.assertNotContains(response, "手動で確認するデータ")
        self.assertNotContains(response, "店舗座標")

    def test_store_planning_page_displays_google_maps_review_grid(self):
        """
        シナリオ:
        - 入力: 対象店舗から半径500m以内にあるGoogle Maps施設レビュー。
        - 処理: 出店計画画面をGETする。
        - 期待値: レビュー概要、3x3グリッド、代表レビューが表示されること。
        """
        place = Place.objects.create(
            place_id="review-place-1",
            name="近隣カフェ",
            location="35.7935,139.8150",
            rating=4.6,
        )
        PlaceReview.objects.create(
            place=place,
            author="reviewer",
            review_text="おいしいランチで雰囲気も良い。おすすめです。",
            publish_time=timezone.now(),
        )

        response = self.client.get(reverse("shp:store_planning"))

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Google Maps レビュー")
        self.assertContains(response, "gmarker に保存済みの Places API レビュー")
        self.assertContains(response, "レビュー対象施設")
        self.assertContains(response, "レビュー数")
        self.assertContains(response, "平均 rating")
        self.assertContains(response, "ポジ / ネガ")
        self.assertContains(response, "1件")
        self.assertContains(response, "4.6")
        self.assertContains(response, "北東")
        self.assertContains(response, "score")
        self.assertContains(response, "近隣カフェ")
        self.assertContains(response, "reviewer")
        self.assertContains(response, "おいしいランチ")
        self.assertNotContains(response, "保存済み Google Maps レビューはありません")

    def test_store_planning_page_restricts_google_maps_clicks_to_superuser(self):
        """
        シナリオ:
        - 入力: 未ログイン状態の出店計画画面URL。
        - 処理: テストクライアントでGETする。
        - 期待値: Google Maps iframe、地図リンク、地図切替ボタンが表示されないこと。
        """
        self.client.logout()

        response = self.client.get(reverse("shp:store_planning"))

        self.assertEqual(200, response.status_code)
        self.assertContains(
            response,
            "Google Maps の表示と外部リンクはスーパーユーザーでログインした場合のみ利用できます。",
        )
        self.assertNotContains(response, "<iframe")
        self.assertNotContains(response, 'class="btn btn-sm store-planning-map-button')
        self.assertNotContains(response, "https://www.google.com/maps?q=35.792822")
        self.assertContains(response, "制限中")

    def test_store_planning_page_selects_registered_sample_store(self):
        """
        シナリオ:
        - 入力: 初期登録済みのOKEI TAPROOMをstoreパラメータに指定したURL。
        - 処理: 出店計画画面をGETする。
        - 期待値: 選択中の対象地点と人口集計条件がOKEI TAPROOMの内容で表示されること。
        """
        response = self.client.get(
            f"{reverse('shp:store_planning')}?store=okei-taproom"
        )

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "OKEI TAPROOM オケタプ")
        self.assertContains(
            response,
            "https://www.google.com/maps?q=35.683713863354235,139.69973314970687",
        )
        self.assertContains(response, "代々木一丁目")
        self.assertContains(response, "e-Stat地域コード 13113")
        self.assertContains(response, "町丁字コード 030001")
        self.assertNotContains(response, "city=13113, town=030001")
        self.assertContains(response, 'value="okei-taproom" selected')

    def test_store_planning_page_uses_selected_store_as_comparison_root(self):
        """
        シナリオ:
        - 入力: OKEI TAPROOMと同じ市区町村・町丁字コードprefixを持つ代々木一丁目から五丁目のe-Stat人口スナップショット。
        - 処理: OKEI TAPROOMを選択して出店計画画面をGETする。
        - 期待値: 代々木一丁目をrootに代々木の地域階層4候補だけが表示され、東保木間の固定候補は混ざらないこと。
        """
        for town_code, small_area_name, total_population in [
            ("030001", "一丁目", 1001),
            ("030002", "二丁目", 1002),
            ("030003", "三丁目", 1003),
            ("030004", "四丁目", 1004),
            ("030005", "五丁目", 1005),
        ]:
            area_name = f"東京都渋谷区代々木{small_area_name}"
            StorePlanningDataSourceSnapshot.objects.create(
                source_key=f"estat_population_age_groups_13113_{town_code}",
                display_name=f"e-Stat 国勢調査 年齢別人口: {area_name}",
                source_url="https://www.e-stat.go.jp/stat-search/files",
                status=f"取得済み: {area_name} の年齢別人口",
                data_period="令和2年国勢調査 小地域集計",
                source_updated_at=timezone.now(),
                raw_data={
                    "stat_inf_id": "000032163275",
                    "resource_id": "000009048041",
                    "table_name": "第3表 男女，年齢（5歳階級）別人口，平均年齢及び総年齢－町丁・字等",
                    "target_area_name": area_name,
                    "prefecture_name": "東京都",
                    "city_name": "渋谷区",
                    "large_area_name": "代々木",
                    "small_area_name": small_area_name,
                    "city_code": "13113",
                    "town_code": town_code,
                    "area_hierarchy_level": "4",
                    "total_population": total_population,
                    "male_population": 500,
                    "female_population": total_population - 500,
                    "average_age": 42.0,
                    "age_groups": [],
                },
            )

        response = self.client.get(
            f"{reverse('shp:store_planning')}?store=okei-taproom"
        )

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "東京都渋谷区代々木一丁目")
        self.assertContains(response, "東京都渋谷区代々木二丁目")
        self.assertContains(response, "東京都渋谷区代々木三丁目")
        self.assertContains(response, "東京都渋谷区代々木四丁目")
        self.assertContains(response, "東京都渋谷区代々木五丁目")
        self.assertContains(response, "030001")
        self.assertContains(response, "030005")
        self.assertContains(response, "1,001人")
        self.assertNotContains(response, "東京都足立区東保木間一丁目")
        self.assertNotContains(
            response, "daily_fetch_store_planning_data_sources を実行してください"
        )

    def test_get_store_planning_target_store_create_page_200(self):
        """
        シナリオ:
        - 入力: 出店計画の店舗登録ページURL。
        - 処理: テストクライアントでGETする。
        - 期待値: HTTP 200 が返され、店舗登録フォームが表示されること。
        """
        response = self.client.get(reverse("shp:store_planning_store_create"))

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "店舗登録")
        self.assertContains(response, "店舗名")
        self.assertContains(response, "E-Stat市区町村コード")
        self.assertContains(response, "E-Stat都道府県名")
        self.assertContains(response, "E-Stat市区町村名")
        self.assertContains(response, "E-Stat大字・町名")
        self.assertContains(response, "E-Stat字・丁目名")
        self.assertContains(response, "Googleマップ座標")
        self.assertContains(response, "e-Stat CSVの「市区町村コード」です")
        self.assertContains(response, "e-Stat CSVの「町丁字コード」です")
        self.assertContains(response, "e-Stat CSVの「都道府県名」です")
        self.assertContains(response, "e-Stat CSVの「市区町村名」です")
        self.assertContains(
            response, "URLの ?store= に入る半角英数字・ハイフンの識別子"
        )
        self.assertContains(response, "e-Stat CSVの「大字・町名」です")
        self.assertContains(response, "e-Stat CSVの「字・丁目名」です")
        self.assertNotContains(response, "E-Stat人口集計地域")
        self.assertNotContains(response, 'name="population_area"')
        self.assertNotContains(response, 'name="latitude"')
        self.assertNotContains(response, 'name="longitude"')
        self.assertNotContains(response, "E-Stat地域階層レベル")

    def test_post_store_planning_target_store_create_page(self):
        """
        シナリオ:
        - 入力: 出店計画の店舗候補として必要な店舗名・Googleマップ座標・e-Stat地域コード。
        - 処理: 店舗登録フォームへPOSTする。
        - 期待値: 店舗候補が保存され、座標と地域階層レベル4が設定されること。
        """
        response = self.client.post(
            reverse("shp:store_planning_store_create"),
            {
                "slug": "test-taproom",
                "name": "Test Taproom",
                "address": "東京都渋谷区代々木",
                "google_maps_coord": "35.1, 139.1",
                "city_code": "13113",
                "town_code": "030002",
                "prefecture_name": "東京都",
                "city_name": "渋谷区",
                "large_area_name": "代々木",
                "small_area_name": "二丁目",
                "is_active": "on",
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('shp:store_planning')}?store=test-taproom",
            fetch_redirect_response=False,
        )
        store = StorePlanningTargetStore.objects.get(slug="test-taproom")
        self.assertEqual(35.1, store.latitude)
        self.assertEqual(139.1, store.longitude)
        self.assertEqual("東京都渋谷区代々木二丁目", store.population_area)
        self.assertEqual("4", store.area_hierarchy_level)

    def test_post_store_planning_target_store_create_page_parses_google_maps_coord(
        self,
    ):
        """
        シナリオ:
        - 入力: Googleマップからコピーした「緯度, 経度」形式の座標。
        - 処理: 店舗登録フォームへPOSTする。
        - 期待値: カンマ区切り座標が緯度・経度に分解されて保存されること。
        """
        response = self.client.post(
            reverse("shp:store_planning_store_create"),
            {
                "slug": "coord-taproom",
                "name": "Coord Taproom",
                "address": "東京都渋谷区代々木",
                "google_maps_coord": "35.683713863354235, 139.69973314970687",
                "city_code": "13113",
                "town_code": "030002",
                "prefecture_name": "東京都",
                "city_name": "渋谷区",
                "large_area_name": "代々木",
                "small_area_name": "二丁目",
                "is_active": "on",
            },
        )

        self.assertRedirects(
            response,
            f"{reverse('shp:store_planning')}?store=coord-taproom",
            fetch_redirect_response=False,
        )
        store = StorePlanningTargetStore.objects.get(slug="coord-taproom")
        self.assertEqual(35.683713863354235, store.latitude)
        self.assertEqual(139.69973314970687, store.longitude)

    def test_post_store_planning_target_store_create_page_rejects_reversed_coord(
        self,
    ):
        """
        シナリオ:
        - 入力: Googleマップ座標欄に「経度, 緯度」の順で座標を入力する。
        - 処理: 店舗登録フォームへPOSTする。
        - 期待値: 緯度の範囲外としてエラーになり、店舗候補が保存されないこと。
        """
        response = self.client.post(
            reverse("shp:store_planning_store_create"),
            {
                "slug": "reversed-coord",
                "name": "Reversed Coord",
                "address": "東京都渋谷区代々木",
                "google_maps_coord": "139.69973314970687, 35.683713863354235",
                "city_code": "13113",
                "town_code": "030002",
                "prefecture_name": "東京都",
                "city_name": "渋谷区",
                "large_area_name": "代々木",
                "small_area_name": "二丁目",
                "is_active": "on",
            },
        )

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "カンマの左側は緯度です")
        self.assertFalse(
            StorePlanningTargetStore.objects.filter(slug="reversed-coord").exists()
        )

    def test_store_planning_page_displays_fallback_sources_before_batch(self):
        """
        シナリオ:
        - 入力: e-Stat人口CSVの集計結果が未保存のDBと、出店計画画面のURL。
        - 処理: テストクライアントでGETする。
        - 期待値: バッチ未実行でも確認対象のデータソース名とデータなし状態が表示されること。
        """
        response = self.client.get(reverse("shp:store_planning"))

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "e-Stat 年代別人口")
        self.assertContains(response, "ファイルID")
        self.assertContains(response, "取得条件")
        self.assertContains(response, "データなし")
        self.assertNotContains(
            response, "daily_fetch_store_planning_data_sources を実行してください"
        )
        self.assertContains(response, "周辺地域比較")
        self.assertContains(response, "地域マップ")
        self.assertContains(response, "<iframe")
        self.assertNotContains(response, "比較対象地域（東保木間一丁目）")
        self.assertContains(response, "e-Stat CSVはまだ取り込まれていません")

    def test_store_planning_page_displays_no_data_for_store_outside_saved_csv(self):
        """
        シナリオ:
        - 入力: 町丁字コードは実在するが、保存済みe-Stat CSVテーブルには未登録の札幌市時計台の店舗候補。
        - 処理: その店舗候補を選択して出店計画画面をGETする。
        - 期待値: 選択店舗をrootにした表示になり、足立区の固定値ではなくデータなしが表示されること。
        """
        response = self.client.get(
            f"{reverse('shp:store_planning')}?store=sapporo-clock-tower"
        )

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "札幌市時計台")
        self.assertContains(response, "データなし表示点検用サンプル")
        self.assertContains(response, "北海道札幌市中央区北一条西二丁目")
        self.assertContains(response, "データなし")
        self.assertNotContains(response, "city=01101, town=790102")
        self.assertNotContains(response, "stat_infid=000032163275")
        self.assertNotContains(response, "000032163275")
        self.assertNotContains(response, "東京都足立区東保木間")
        self.assertNotContains(response, "東京都渋谷区代々木")
        self.assertNotContains(
            response, "daily_fetch_store_planning_data_sources を実行してください"
        )

    def test_store_planning_page_ignores_comparison_area_as_store_selection(self):
        """
        シナリオ:
        - 入力: 比較対象地域のe-Stat人口スナップショットと、比較対象地域slugを指定したURL。
        - 処理: 出店計画画面をGETする。
        - 期待値: 店舗候補はChapter Tableのまま、比較対象地域として東保木間一丁目が表示されること。
        """
        StorePlanningDataSourceSnapshot.objects.create(
            source_key="estat_population_age_groups_13121_073001",
            display_name="e-Stat 国勢調査 年齢別人口: 東京都足立区東保木間一丁目",
            source_url="https://www.e-stat.go.jp/stat-search/files",
            status="取得済み: 東京都足立区東保木間一丁目 の年齢別人口",
            data_period="令和2年国勢調査 小地域集計",
            source_updated_at=timezone.now(),
            raw_data={
                "stat_inf_id": "000032163275",
                "resource_id": "000009048041",
                "table_name": "第3表 男女，年齢（5歳階級）別人口，平均年齢及び総年齢－町丁・字等",
                "target_area_name": "東京都足立区東保木間一丁目",
                "prefecture_name": "東京都",
                "city_name": "足立区",
                "city_code": "13121",
                "town_code": "073001",
                "area_hierarchy_level": "4",
                "total_population": 1234,
                "male_population": 600,
                "female_population": 634,
                "average_age": 44.1,
                "age_groups": [
                    {
                        "label": "0代",
                        "population": 110,
                        "male_population": 55,
                        "female_population": 55,
                    },
                ],
            },
        )

        url = f"{reverse('shp:store_planning')}?store=area-higashi-hokima-1"
        response = self.client.get(url)

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "Chapter Table")
        self.assertContains(response, "東京都足立区東保木間二丁目")
        self.assertContains(response, "東京都足立区東保木間一丁目")
        self.assertContains(response, "自動候補")
        self.assertContains(response, "1,234人")
        self.assertContains(response, "073001")
        self.assertContains(response, "周辺地域比較")
        self.assertContains(response, "output=embed")
        self.assertContains(response, "073002")

    def test_store_planning_page_displays_estat_code_based_comparison_candidates(
        self,
    ):
        """
        シナリオ:
        - 入力: 対象地域と同じ市区町村・地域階層レベル4・町丁字コード先頭2桁を持つe-Stat人口スナップショット。
        - 処理: 出店計画画面をGETする。
        - 期待値: 手動比較対象ではなく、e-Stat地域コードから抽出した比較候補が表示されること。
        """
        StorePlanningDataSourceSnapshot.objects.create(
            source_key="estat_population_age_groups_13121_073002",
            display_name="e-Stat 国勢調査 年齢別人口: 東京都足立区東保木間二丁目",
            source_url="https://www.e-stat.go.jp/stat-search/files",
            status="取得済み: 東京都足立区東保木間二丁目 の年齢別人口",
            data_period="令和2年国勢調査 小地域集計",
            source_updated_at=timezone.now(),
            raw_data={
                "stat_inf_id": "000032163275",
                "resource_id": "000009048041",
                "table_name": "第3表 男女，年齢（5歳階級）別人口，平均年齢及び総年齢－町丁・字等",
                "target_area_name": "東京都足立区東保木間二丁目",
                "prefecture_name": "東京都",
                "city_name": "足立区",
                "large_area_name": "東保木間",
                "small_area_name": "二丁目",
                "city_code": "13121",
                "town_code": "073002",
                "area_hierarchy_level": "4",
                "total_population": 2289,
                "average_age": 43.8,
                "age_groups": [],
            },
        )
        StorePlanningDataSourceSnapshot.objects.create(
            source_key="estat_population_age_groups_13121",
            display_name="e-Stat 国勢調査 年齢別人口: 東京都足立区",
            source_url="https://www.e-stat.go.jp/stat-search/files",
            status="取得済み: 東京都足立区 の年齢別人口",
            data_period="令和2年国勢調査 小地域集計",
            source_updated_at=timezone.now(),
            raw_data={
                "target_area_name": "東京都足立区",
                "prefecture_name": "東京都",
                "city_name": "足立区",
                "city_code": "13121",
                "area_hierarchy_level": "1",
                "age_groups": [],
            },
        )
        StorePlanningDataSourceSnapshot.objects.create(
            source_key="estat_population_age_groups_13121_0730",
            display_name="e-Stat 国勢調査 年齢別人口: 東京都足立区東保木間",
            source_url="https://www.e-stat.go.jp/stat-search/files",
            status="取得済み: 東京都足立区東保木間 の年齢別人口",
            data_period="令和2年国勢調査 小地域集計",
            source_updated_at=timezone.now(),
            raw_data={
                "target_area_name": "東京都足立区東保木間",
                "large_area_name": "東保木間",
                "city_code": "13121",
                "town_code": "0730",
                "area_hierarchy_level": "3",
                "total_population": 1300,
                "age_groups": [],
            },
        )
        StorePlanningDataSourceSnapshot.objects.create(
            source_key="estat_population_age_groups_13121_073001",
            display_name="e-Stat 国勢調査 年齢別人口: 東京都足立区東保木間一丁目",
            source_url="https://www.e-stat.go.jp/stat-search/files",
            status="取得済み: 東京都足立区東保木間一丁目 の年齢別人口",
            data_period="令和2年国勢調査 小地域集計",
            source_updated_at=timezone.now(),
            raw_data={
                "stat_inf_id": "000032163275",
                "resource_id": "000009048041",
                "table_name": "第3表 男女，年齢（5歳階級）別人口，平均年齢及び総年齢－町丁・字等",
                "target_area_name": "東京都足立区東保木間一丁目",
                "prefecture_name": "東京都",
                "city_name": "足立区",
                "large_area_name": "東保木間",
                "small_area_name": "一丁目",
                "city_code": "13121",
                "town_code": "073001",
                "area_hierarchy_level": "4",
                "total_population": 1400,
                "average_age": 45.2,
                "age_groups": [],
            },
        )
        StorePlanningDataSourceSnapshot.objects.create(
            source_key="estat_population_age_groups_13121_076001",
            display_name="e-Stat 国勢調査 年齢別人口: 東京都足立区保木間一丁目",
            source_url="https://www.e-stat.go.jp/stat-search/files",
            status="取得済み: 東京都足立区保木間一丁目 の年齢別人口",
            data_period="令和2年国勢調査 小地域集計",
            source_updated_at=timezone.now(),
            raw_data={
                "target_area_name": "東京都足立区保木間一丁目",
                "large_area_name": "保木間",
                "city_code": "13121",
                "town_code": "076001",
                "area_hierarchy_level": "4",
                "total_population": 999,
                "age_groups": [],
            },
        )
        StorePlanningDataSourceSnapshot.objects.create(
            source_key="estat_population_age_groups_13121_070001",
            display_name="e-Stat 国勢調査 年齢別人口: 東京都足立区東伊興一丁目",
            source_url="https://www.e-stat.go.jp/stat-search/files",
            status="取得済み: 東京都足立区東伊興一丁目 の年齢別人口",
            data_period="令和2年国勢調査 小地域集計",
            source_updated_at=timezone.now(),
            raw_data={
                "target_area_name": "東京都足立区東伊興一丁目",
                "large_area_name": "東伊興",
                "city_code": "13121",
                "town_code": "070001",
                "area_hierarchy_level": "4",
                "total_population": 9999,
                "age_groups": [],
            },
        )

        response = self.client.get(reverse("shp:store_planning"))

        self.assertEqual(200, response.status_code)
        self.assertContains(response, "東京都足立区東保木間")
        self.assertContains(response, "東京都足立区東保木間一丁目")
        self.assertContains(response, "広域")
        self.assertContains(response, "地域階層レベル3")
        self.assertContains(response, "町丁")
        self.assertContains(response, "地域階層レベル4")
        self.assertContains(response, "0730")
        self.assertContains(response, "073001")
        self.assertContains(response, "レベル 3")
        self.assertContains(response, "レベル 4")
        self.assertContains(
            response,
            "https://www.google.com/maps?q=%E6%9D%B1%E4%BA%AC%E9%83%BD%E8%B6%B3%E7%AB%8B%E5%8C%BA%E6%9D%B1%E4%BF%9D%E6%9C%A8%E9%96%93&amp;output=embed",
        )
        self.assertContains(
            response,
            "https://www.google.com/maps?q=%E6%9D%B1%E4%BA%AC%E9%83%BD%E8%B6%B3%E7%AB%8B%E5%8C%BA%E6%9D%B1%E4%BF%9D%E6%9C%A8%E9%96%93%E4%BA%8C%E4%B8%81%E7%9B%AE&amp;output=embed",
        )
        self.assertContains(
            response,
            "市区町村コード・地域階層レベル4・町丁字コード先頭2桁から抽出（境界未確認）",
        )
        self.assertContains(response, "地域検索")
        self.assertContains(response, "e-Stat CSV カバー範囲")
        self.assertContains(response, "東京都 足立区")
        self.assertContains(response, "4件")
        self.assertNotContains(response, "東京都足立区東伊興一丁目")
        self.assertNotContains(response, "東京都足立区保木間一丁目")
        self.assertNotContains(response, "9,999人")
        self.assertNotContains(response, "999人")

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
