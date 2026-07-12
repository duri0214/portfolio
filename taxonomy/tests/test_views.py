import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.test import SimpleTestCase
from django.test import TestCase
from django.urls import reverse

from taxonomy.domain.service.livestock_distribution_fetch import (
    LivestockDistributionFetchService,
    TABLE_DEFINITIONS,
)
from taxonomy.models import (
    Breed,
    Classification,
    Family,
    Genus,
    Kingdom,
    LivestockDistributionDataset,
    NaturalMonument,
    Phylum,
    Species,
)


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TaxonomyIndexViewTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._overridden_settings["MEDIA_ROOT"], ignore_errors=True)
        super().tearDownClass()

    def test_index_page_wraps_classification_chart_in_scroll_area(self):
        """
        シナリオ:
        - 入力: taxonomyの分類データが空でも表示できるDB状態。
        - 処理: 分類グラフを含むtaxonomyトップページを表示する。
        - 期待値: 分類グラフが途中で切れないよう、スクロール可能な領域で囲まれていること。
        """
        response = self.client.get(reverse("txo:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "taxonomy-chart-scroll")
        self.assertContains(response, "overflow-x: hidden")
        self.assertContains(response, "overflow-y: visible")
        self.assertContains(response, "countClassificationNodes")
        self.assertContains(response, "fitClassificationChartHeight")

    def test_index_page_shows_taxonomy_hierarchy_guidance(self):
        """
        シナリオ:
        - 入力: taxonomyトップページを表示できるDB状態。
        - 処理: taxonomyトップページを表示する。
        - 期待値: 分類体系の入れ子構造とValue Objectの説明が表示されること。
        """
        response = self.client.get(reverse("txo:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "分類体系の入れ子構造")
        self.assertContains(response, "霊長類の下にヒトが紐づく")
        self.assertContains(response, "Value Object")
        self.assertContains(
            response, '<i class="fas fa-chart-area me-1"></i>鶏の観察グラフ'
        )
        self.assertNotContains(response, "e-Stat 畜産統計による鶏の地域別飼養分布")
        self.assertNotContains(response, "livestock-prefecture-map")
        self.assertNotContains(response, "鶏の観察グラフへ")

    def test_observation_page_shows_livestock_distribution_upload_form(self):
        """
        シナリオ:
        - 入力: 畜産統計データが未取得のDB状態。
        - 処理: 鶏の観察グラフページを表示する。
        - 期待値: e-Stat API取得ボタンと、空の日本地図用コンテナが表示されること。
        """
        response = self.client.get(reverse("txo:observation"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "畜産統計データ取得")
        self.assertContains(response, "畜産統計データはまだ取得されていません。")
        self.assertContains(response, "政府統計コード")
        self.assertContains(response, "00500222")
        self.assertContains(
            response,
            "https://www.e-stat.go.jp/stat-search/files?toukei=00500222",
        )
        self.assertContains(response, "指定年度の畜産統計")
        self.assertContains(response, "APIレスポンスを表示用CSVスナップショット")
        self.assertContains(response, "取得年度")
        self.assertContains(response, 'name="livestock_survey_year"')
        self.assertContains(response, "disabled")
        self.assertContains(
            response,
            "管理者権限が必要なため、データ取得ボタンは無効化されています。",
        )
        self.assertContains(response, "畜産統計データ未取得")
        self.assertContains(response, "livestock-distribution-data")
        self.assertContains(response, "livestock-prefecture-map")
        self.assertContains(response, "e-Stat畜産統計データを取得")

    def test_observation_page_displays_livestock_distribution_dashboard(self):
        """
        シナリオ:
        - 入力: 畜産統計データが取得済みのDB状態。
        - 処理: 鶏の観察グラフページを表示する。
        - 期待値: e-Stat畜産統計の採卵鶏・ブロイラー可視化に必要なメタ情報とJSONが表示されること。
        """
        self._create_livestock_dataset()

        response = self.client.get(reverse("txo:observation"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "e-Stat 畜産統計による鶏の地域別飼養分布")
        self.assertContains(response, "政府統計コード")
        self.assertContains(response, "00500222")
        self.assertContains(response, "https://www.e-stat.go.jp/stat-search/files")
        self.assertContains(response, "採卵鶏")
        self.assertContains(response, "ブロイラー")
        self.assertContains(
            response, "採卵鶏とブロイラーは、飼育目的が異なる統計分類です。"
        )
        self.assertContains(response, "ブロイラーの雌も生物として卵を産めます")
        self.assertContains(response, "livestock-distribution-data")
        self.assertContains(response, "livestock-prefecture-map")
        self.assertContains(response, "分類内の全国比")
        self.assertContains(response, "秘匿・該当なし")

    def test_observation_page_displays_latest_livestock_distribution_by_default(self):
        """
        シナリオ:
        - 入力: 2024年と2025年の畜産統計データが取得済みのDB状態。
        - 処理: 対象年を指定せずに鶏の観察グラフページを表示する。
        - 期待値: 最新取得日の2025年データが初期表示され、対象年選択肢が表示されること。
        """
        self._create_livestock_dataset(
            title="令和6年畜産統計",
            survey_year=2024,
            retrieved_at="2026-07-10",
        )
        self._create_livestock_dataset(
            title="令和7年畜産統計",
            survey_year=2025,
            retrieved_at="2026-07-11",
        )

        response = self.client.get(reverse("txo:observation"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["livestock_dashboard"].survey_year, 2025)
        self.assertContains(response, "対象年")
        self.assertContains(response, 'value="2025"')
        self.assertContains(response, 'value="2024"')
        self.assertContains(response, "2025年 /")

    def test_observation_page_can_select_past_livestock_distribution_year(self):
        """
        シナリオ:
        - 入力: 2024年と2025年の畜産統計データが取得済みのDB状態。
        - 処理: 2024年を指定して鶏の観察グラフページを表示する。
        - 期待値: 最新年ではなく選択した2024年データが表示されること。
        """
        self._create_livestock_dataset(
            title="令和6年畜産統計",
            survey_year=2024,
            retrieved_at="2026-07-10",
        )
        self._create_livestock_dataset(
            title="令和7年畜産統計",
            survey_year=2025,
            retrieved_at="2026-07-11",
        )

        response = self.client.get(
            reverse("txo:observation"),
            {"livestock_year": "2024"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["livestock_dashboard"].survey_year, 2024)
        self.assertEqual(response.context["selected_livestock_survey_year"], 2024)
        self.assertContains(response, "2024年 /")
        self.assertContains(response, "取得日 2026-07-10")

    def test_observation_page_shows_empty_map_for_unregistered_or_inactive_year(self):
        """
        シナリオ:
        - 入力: 2024年の有効データと2023年の無効データが登録済みのDB状態。
        - 処理: 無効な2023年を指定して鶏の観察グラフページを表示する。
        - 期待値: 無効データは表示せず、空の日本地図と未登録状態が表示されること。
        """
        self._create_livestock_dataset(
            title="令和6年畜産統計",
            survey_year=2024,
            retrieved_at="2026-07-10",
        )
        self._create_livestock_dataset(
            title="令和5年畜産統計",
            survey_year=2023,
            retrieved_at="2026-07-09",
            is_active=False,
        )

        response = self.client.get(
            reverse("txo:observation"),
            {"livestock_year": "2023"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["livestock_dashboard"])
        self.assertEqual(response.context["selected_livestock_survey_year"], 2023)
        self.assertContains(response, "2023年の畜産統計データは未取得または無効です。")
        self.assertContains(response, "livestock-prefecture-map")
        self.assertContains(response, "畜産統計データ未取得")

        unregistered_response = self.client.get(
            reverse("txo:observation"),
            {"livestock_year": "2022"},
        )

        self.assertEqual(unregistered_response.status_code, 200)
        self.assertIsNone(unregistered_response.context["livestock_dashboard"])
        self.assertEqual(
            unregistered_response.context["selected_livestock_survey_year"], 2022
        )
        self.assertContains(
            unregistered_response, "2022年の畜産統計データは未取得または無効です。"
        )

    def test_observation_page_ignores_dataset_when_csv_file_is_missing(self):
        """
        シナリオ:
        - 入力: 有効な畜産統計データセットのDBレコードはあるが、CSV実体が欠損している状態。
        - 処理: 鶏の観察グラフページを表示する。
        - 期待値: FileNotFoundError にせず、未取得状態として空の地図を表示すること。
        """
        dataset = self._create_livestock_dataset()
        dataset.csv_file.storage.delete(dataset.csv_file.name)

        response = self.client.get(reverse("txo:observation"))

        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["livestock_dashboard"])
        self.assertEqual(response.context["livestock_survey_years"], [])
        self.assertContains(response, "畜産統計データはまだ取得されていません。")
        self.assertContains(response, "livestock-prefecture-map")

    @patch.dict("os.environ", {"ESTAT_APP_ID": "fake-app-id"})
    @patch("taxonomy.domain.dataprovider.estat.requests.get")
    def test_superuser_can_fetch_livestock_distribution_dataset(self, mock_get):
        """
        シナリオ:
        - 入力: スーパーユーザーとe-Stat APIの畜産統計レスポンス。
        - 処理: 鶏の観察グラフページの取得ボタンをPOSTする。
        - 期待値: データセットが作成され、取得件数・対象年・取得日とダッシュボードが表示されること。
        """
        mock_get.side_effect = [
            _mock_estat_list_response("layers", "0004041877"),
            _mock_estat_response("layers", "採卵鶏", "1,640", "170,776"),
            _mock_estat_list_response("broilers", "0004041880"),
            _mock_estat_response("broilers", "ブロイラー", "2,050", "144,859"),
        ]
        user = get_user_model().objects.create_superuser(
            username="taxonomy_admin",
            email="taxonomy_admin@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("txo:observation"),
            {"livestock_survey_year": "2024"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(LivestockDistributionDataset.objects.count(), 1)
        self.assertContains(response, "畜産統計データを取得しました。")
        self.assertContains(response, "対象年: 2024年")
        self.assertContains(response, "登録件数: 96件")
        self.assertContains(response, "取得日:")
        self.assertContains(response, "e-Stat 畜産統計による鶏の地域別飼養分布")
        list_params = mock_get.call_args_list[0].kwargs["params"]
        self.assertEqual(list_params["appId"], "fake-app-id")
        self.assertEqual(list_params["surveyYears"], "20240")
        self.assertIn("採卵鶏", list_params["searchWord"])
        data_params = mock_get.call_args_list[1].kwargs["params"]
        self.assertEqual(data_params["statsDataId"], "0004041877")

    @patch.dict("os.environ", {"ESTAT_APP_ID": "fake-app-id"})
    def test_superuser_fetch_livestock_distribution_requires_survey_year(self):
        """
        シナリオ:
        - 入力: 取得年度が未入力のPOSTとスーパーユーザー。
        - 処理: 鶏の観察グラフページの取得ボタンをPOSTする。
        - 期待値: APIを呼び出さず、取得年度の入力エラーが表示されること。
        """
        user = get_user_model().objects.create_superuser(
            username="taxonomy_admin",
            email="taxonomy_admin@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.post(reverse("txo:observation"), follow=True)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(LivestockDistributionDataset.objects.count(), 0)
        self.assertContains(response, "取得年度は西暦の数値で指定してください。")

    @patch.dict("os.environ", {"ESTAT_APP_ID": ""})
    def test_superuser_fetch_livestock_distribution_requires_estat_app_id(self):
        """
        シナリオ:
        - 入力: ESTAT_APP_ID が未設定の環境とスーパーユーザー。
        - 処理: 鶏の観察グラフページの取得ボタンをPOSTする。
        - 期待値: APIを呼び出さず、未設定エラーが表示されること。
        """
        user = get_user_model().objects.create_superuser(
            username="taxonomy_admin",
            email="taxonomy_admin@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("txo:observation"),
            {"livestock_survey_year": "2024"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(LivestockDistributionDataset.objects.count(), 0)
        self.assertContains(response, "ESTAT_APP_ID が未設定")

    @patch.dict("os.environ", {"ESTAT_APP_ID": "fake-app-id"})
    @patch("taxonomy.domain.dataprovider.estat.requests.get")
    def test_superuser_fetch_livestock_distribution_shows_api_error(self, mock_get):
        """
        シナリオ:
        - 入力: e-Stat API取得で例外が発生する状態とスーパーユーザー。
        - 処理: 鶏の観察グラフページの取得ボタンをPOSTする。
        - 期待値: API取得失敗としてメッセージが表示され、データセットは作成されないこと。
        """
        mock_get.side_effect = RuntimeError("network error")
        user = get_user_model().objects.create_superuser(
            username="taxonomy_admin",
            email="taxonomy_admin@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("txo:observation"),
            {"livestock_survey_year": "2024"},
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(LivestockDistributionDataset.objects.count(), 0)
        self.assertContains(response, "API取得失敗")

    def test_livestock_distribution_fetch_parses_estat_cat01_response(self):
        """
        シナリオ:
        - 入力: 実e-Statに近い @cat01 と都道府県_青森形式の畜産統計レスポンス。
        - 処理: 採卵鶏のレスポンスを表示用CSV行へ変換する。
        - 期待値: 県 suffix なしの地域名とcat01分類から、
          全国・47都道府県の戸数と羽数を取得できること。
        """
        response = _estat_payload(
            "layers",
            "採卵鶏",
            "1,640",
            "170,776",
            area_key="area",
            item_key="cat01",
            item_labels=(
                "飼養戸数_採卵鶏",
                "飼養羽数_計",
            ),
            prefecture_suffix=False,
        )
        statistical_data = response["GET_STATS_DATA"]["STATISTICAL_DATA"]
        statistical_data["CLASS_INF"]["CLASS_OBJ"][1]["CLASS"].append(
            {"@code": "003", "@name": "飼養戸数_種鶏のみ"}
        )
        for area in statistical_data["CLASS_INF"]["CLASS_OBJ"][0]["CLASS"]:
            statistical_data["DATA_INF"]["VALUE"].append(
                {"@area": area["@code"], "@cat01": "003", "$": "999"}
            )

        rows = LivestockDistributionFetchService._parse_rows(
            TABLE_DEFINITIONS[0],
            response,
        )

        self.assertEqual(len(rows), 48)
        self.assertEqual(rows[0].prefecture, "全国")
        self.assertEqual(rows[0].households, 1640)
        self.assertEqual(rows[0].birds_thousand, 170776)
        self.assertEqual(rows[2].prefecture, "青森県")
        self.assertEqual(rows[2].households, 10)
        self.assertEqual(rows[2].birds_thousand, 100)

    def test_rejects_livestock_distribution_upload_without_permission(self):
        """
        シナリオ:
        - 入力: 未ログインユーザー。
        - 処理: 鶏の観察グラフページへ取得ボタンをPOSTする。
        - 期待値: データセットは作成されず、権限エラーが表示されること。
        """
        response = self.client.post(
            reverse("txo:observation"),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(LivestockDistributionDataset.objects.count(), 0)
        self.assertContains(response, "畜産統計データを取得する権限がありません。")

    def _create_livestock_dataset(
        self,
        title="令和6年畜産統計",
        survey_year=2024,
        retrieved_at="2026-07-11",
        is_active=True,
    ):
        return LivestockDistributionDataset.objects.create(
            title=title,
            csv_file=SimpleUploadedFile(
                f"livestock_{survey_year}.csv",
                _livestock_distribution_csv().encode("utf-8"),
                content_type="text/csv",
            ),
            source_name="e-Stat / 農林水産省 畜産統計調査",
            source_stat_code="00500222",
            survey_year=survey_year,
            retrieved_at=retrieved_at,
            source_url="https://www.e-stat.go.jp/stat-search/files",
            note=(
                "令和6年2月1日現在。単位は千羽。e-Statの秘匿値 x と"
                "該当なし - は推計せず秘匿・該当なしとして表示します。"
            ),
            is_active=is_active,
        )


class LivestockDistributionStaticAssetTest(SimpleTestCase):
    def test_livestock_distribution_js_labels_comparison_bar_clearly(self):
        """
        シナリオ:
        - 入力: 畜産統計ダッシュボード用のJavaScriptファイル。
        - 処理: 静的ファイルの内容を読み込む。
        - 期待値: 採卵鶏・ブロイラーの比率バーが何を表すか分かる文言で表示されること。
        """
        script_path = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "taxonomy"
            / "js"
            / "livestock_distribution.js"
        )
        script = script_path.read_text(encoding="utf-8")

        self.assertIn("全国羽数の内訳", script)
        self.assertIn("どちらが多いか", script)
        self.assertIn("2分類合計内の割合", script)
        self.assertIn("分類内の全国比", script)
        self.assertIn("getBoundingClientRect", script)


def _livestock_distribution_csv():
    rows = [
        "category_key,category_label,table_number,table_title,prefecture_code,prefecture,households,birds_thousand",
        "layers,採卵鶏,1,採卵鶏の飼養戸数・羽数,0,全国,2000,170776",
        "broilers,ブロイラー,2,ブロイラーの飼養戸数・羽数,0,全国,1000,144859",
    ]
    for code in range(1, 48):
        rows.append(
            f"layers,採卵鶏,1,採卵鶏の飼養戸数・羽数,{code},都道府県{code},10,100"
        )

    for code in range(1, 48):
        prefecture = "栃木県" if code == 9 else f"都道府県{code}"
        birds = "" if code == 9 else "80"
        rows.append(
            f"broilers,ブロイラー,2,ブロイラーの飼養戸数・羽数,{code},{prefecture},8,{birds}"
        )

    return "\n".join(rows)


def _mock_estat_response(
    category_key, category_label, national_households, national_birds
):
    response = type("Response", (), {})()
    response.raise_for_status = lambda: None
    response.json = lambda: _estat_payload(
        category_key,
        category_label,
        national_households,
        national_birds,
    )
    return response


def _mock_estat_list_response(category_key, stats_data_id):
    response = type("Response", (), {})()
    response.raise_for_status = lambda: None
    category_label = "採卵鶏" if category_key == "layers" else "ブロイラー"
    response.json = lambda: {
        "GET_STATS_LIST": {
            "DATALIST_INF": {
                "TABLE_INF": {
                    "@id": stats_data_id,
                    "STATISTICS_NAME": "畜産統計調査 確報 令和6年畜産統計",
                    "TITLE": (
                        f"{category_label}の飼養戸数・羽数"
                        "（全国農業地域・都道府県別）"
                    ),
                }
            }
        }
    }
    return response


def _estat_payload(
    category_key,
    category_label,
    national_households,
    national_birds,
    area_key="area",
    item_key="tab",
    item_labels=None,
    prefecture_suffix=True,
):
    item_labels = item_labels or (
        f"{category_label}飼養戸数",
        f"{category_label}飼養羽数",
    )
    values = [
        {f"@{area_key}": "00000", f"@{item_key}": "001", "$": national_households},
        {f"@{area_key}": "00000", f"@{item_key}": "002", "$": national_birds},
    ]
    class_items = [{"@code": "00000", "@name": "全国"}]
    prefectures = [
        "北海道",
        "青森県",
        "岩手県",
        "宮城県",
        "秋田県",
        "山形県",
        "福島県",
        "茨城県",
        "栃木県",
        "群馬県",
        "埼玉県",
        "千葉県",
        "東京都",
        "神奈川県",
        "新潟県",
        "富山県",
        "石川県",
        "福井県",
        "山梨県",
        "長野県",
        "岐阜県",
        "静岡県",
        "愛知県",
        "三重県",
        "滋賀県",
        "京都府",
        "大阪府",
        "兵庫県",
        "奈良県",
        "和歌山県",
        "鳥取県",
        "島根県",
        "岡山県",
        "広島県",
        "山口県",
        "徳島県",
        "香川県",
        "愛媛県",
        "高知県",
        "福岡県",
        "佐賀県",
        "長崎県",
        "熊本県",
        "大分県",
        "宮崎県",
        "鹿児島県",
        "沖縄県",
    ]
    for index, prefecture in enumerate(prefectures, start=1):
        area_code = f"{index:05d}"
        prefecture_label = prefecture
        if not prefecture_suffix and prefecture != "北海道":
            prefecture_label = (
                prefecture.removesuffix("都").removesuffix("府").removesuffix("県")
            )
        class_items.append(
            {"@code": area_code, "@name": f"都道府県_{prefecture_label}"}
        )
        values.append({f"@{area_key}": area_code, f"@{item_key}": "001", "$": "10"})
        birds = "x" if category_key == "broilers" and prefecture == "栃木県" else "100"
        values.append({f"@{area_key}": area_code, f"@{item_key}": "002", "$": birds})

    return {
        "GET_STATS_DATA": {
            "STATISTICAL_DATA": {
                "CLASS_INF": {
                    "CLASS_OBJ": [
                        {"@id": area_key, "CLASS": class_items},
                        {
                            "@id": item_key,
                            "CLASS": [
                                {"@code": "001", "@name": item_labels[0]},
                                {"@code": "002", "@name": item_labels[1]},
                            ],
                        },
                    ]
                },
                "DATA_INF": {"VALUE": values},
            }
        }
    }


@override_settings(MEDIA_ROOT=tempfile.mkdtemp())
class TaxonomyBreedCreateViewTest(TestCase):
    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls._overridden_settings["MEDIA_ROOT"], ignore_errors=True)
        super().tearDownClass()

    def setUp(self):
        self.kingdom = Kingdom.objects.create(name="動物界", name_en="Animalia")
        self.phylum = Phylum.objects.create(
            name="脊索動物門", name_en="Chordata", kingdom=self.kingdom
        )
        self.classification = Classification.objects.create(
            name="鳥綱", name_en="Aves", phylum=self.phylum
        )
        self.family = Family.objects.create(
            name="キジ科", name_en="Phasianidae", classification=self.classification
        )
        self.genus = Genus.objects.create(
            name="ヤケイ属", name_en="Gallus", family=self.family
        )
        self.species = Species.objects.create(
            name="ニワトリ", name_en="Gallus gallus domesticus", genus=self.genus
        )
        self.natural_monument = NaturalMonument.objects.create(name="天然記念物")

    def test_create_page_shows_hierarchy_and_breed_fields(self):
        """
        シナリオ:
        - 入力: 既存の分類階層が登録済みのDB状態。
        - 処理: 分類登録ページを表示する。
        - 期待値: 階層選択と品種登録に必要な入力欄が表示されること。
        """
        response = self.client.get(reverse("txo:breed_new"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "分類登録")
        self.assertContains(response, "既存の界")
        self.assertContains(response, 'aria-label="分類の中での位置"')
        self.assertContains(response, "badge bg-primary")
        self.assertContains(response, "体の基本構造や進化的なまとまり")
        self.assertContains(response, "品種・系統・分類対象名")
        self.assertContains(response, "hierarchyOptions")
        self.assertContains(response, "updateNewFieldState")

    def test_create_breed_with_existing_hierarchy(self):
        """
        シナリオ:
        - 入力: 既存の分類階層と未登録の品種名。
        - 処理: 分類登録フォームをPOSTする。
        - 期待値: 選択した種に紐づく品種が作成され、トップページへ戻ること。
        """
        response = self.client.post(
            reverse("txo:breed_new"),
            data=self._base_post_data({"breed_name": "名古屋種"}),
        )

        breed = Breed.objects.get(name="名古屋種")
        self.assertRedirects(response, reverse("txo:breed_detail", args=[breed.pk]))
        self.assertEqual(breed.species, self.species)

    def test_create_breed_without_image(self):
        """
        シナリオ:
        - 入力: 既存の分類階層と画像未添付の品種情報。
        - 処理: 分類登録フォームをPOSTする。
        - 期待値: 画像がなくても品種が作成され、トップページへ戻ること。
        """
        data = self._base_post_data({"breed_name": "写真なし系統"})
        data.pop("breed_image")

        response = self.client.post(reverse("txo:breed_new"), data=data)

        breed = Breed.objects.get(name="写真なし系統")
        self.assertRedirects(response, reverse("txo:breed_detail", args=[breed.pk]))
        self.assertEqual(breed.image.name, "")

    def test_create_breed_allows_empty_optional_fields(self):
        """
        シナリオ:
        - 入力: 既存の分類階層と任意項目未入力の品種情報。
        - 処理: メモと天然記念物区分を空欄にして分類登録フォームをPOSTする。
        - 期待値: 品種が作成され、任意項目が空として保存されること。
        """
        data = self._base_post_data({"breed_name": "任意項目なし系統"})
        data.update(
            {
                "breed_remark": "",
                "natural_monument": "",
            }
        )

        response = self.client.post(reverse("txo:breed_new"), data=data)

        breed = Breed.objects.get(name="任意項目なし系統")
        self.assertRedirects(response, reverse("txo:breed_detail", args=[breed.pk]))
        self.assertIsNone(breed.remark)
        self.assertIsNone(breed.natural_monument)

    def test_create_breed_with_new_hierarchy(self):
        """
        シナリオ:
        - 入力: 既存階層を選ばず、各階層の新しい名前と品種情報を入力する。
        - 処理: 分類登録フォームをPOSTする。
        - 期待値: 新しい階層と品種がまとめて作成されること。
        """
        response = self.client.post(
            reverse("txo:breed_new"),
            data={
                "kingdom_name": "動物界",
                "kingdom_name_en": "Animalia",
                "phylum_name": "環形動物門",
                "phylum_name_en": "Annelida",
                "classification_name": "貧毛綱",
                "classification_name_en": "Oligochaeta",
                "family_name": "フトミミズ科",
                "family_name_en": "Megascolecidae",
                "genus_name": "フトミミズ属",
                "genus_name_en": "Pheretima",
                "species_name": "フトミミズ",
                "species_name_en": "Pheretima communissima",
                "breed_name": "畑土系統",
                "breed_name_kana": "はたけつちけいとう",
                "breed_image": self._image("new.gif"),
            },
        )

        breed = Breed.objects.select_related("species__genus").get(name="畑土系統")
        self.assertRedirects(response, reverse("txo:breed_detail", args=[breed.pk]))
        self.assertEqual(breed.species.name, "フトミミズ")
        self.assertEqual(breed.species.genus.name, "フトミミズ属")

    def test_index_page_links_to_breed_list(self):
        """
        シナリオ:
        - 入力: taxonomyトップページを表示できるDB状態。
        - 処理: taxonomyトップページを表示する。
        - 期待値: 品種一覧ページへの導線が表示されること。
        """
        response = self.client.get(reverse("txo:index"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("txo:breed_list"))
        self.assertContains(response, "品種一覧")

    def test_breed_list_shows_action_links(self):
        """
        シナリオ:
        - 入力: 品種が1件登録済みのDB状態。
        - 処理: 品種一覧ページを表示する。
        - 期待値: 詳細・編集・削除の操作導線が表示されること。
        """
        breed = self._create_breed(name="烏骨鶏")

        response = self.client.get(reverse("txo:breed_list"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "烏骨鶏")
        self.assertContains(response, reverse("txo:breed_detail", args=[breed.pk]))
        self.assertContains(response, reverse("txo:breed_edit", args=[breed.pk]))
        self.assertContains(response, reverse("txo:breed_delete", args=[breed.pk]))

    def test_breed_detail_shows_hierarchy_and_navigation(self):
        """
        シナリオ:
        - 入力: 分類階層に紐づく品種が登録済みのDB状態。
        - 処理: 品種詳細ページを表示する。
        - 期待値: 界から品種までの階層情報と一覧・編集への導線が表示されること。
        """
        breed = self._create_breed(name="名古屋種")

        response = self.client.get(reverse("txo:breed_detail", args=[breed.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "動物界")
        self.assertContains(response, "脊索動物門")
        self.assertContains(response, "鳥綱")
        self.assertContains(response, "キジ科")
        self.assertContains(response, "ヤケイ属")
        self.assertContains(response, "ニワトリ")
        self.assertContains(response, "名古屋種")
        self.assertContains(response, reverse("txo:breed_list"))
        self.assertContains(response, reverse("txo:breed_edit", args=[breed.pk]))

    def test_edit_breed_updates_record_and_redirects_to_detail(self):
        """
        シナリオ:
        - 入力: 登録済みの品種と更新後の品種情報。
        - 処理: 品種編集フォームをPOSTする。
        - 期待値: 品種情報が更新され、詳細ページへ戻ること。
        """
        breed = self._create_breed(name="烏骨鶏")

        response = self.client.post(
            reverse("txo:breed_edit", args=[breed.pk]),
            data={
                "species": self.species.pk,
                "name": "更新した烏骨鶏",
                "name_kana": "こうしんしたうこっけい",
                "natural_monument": self.natural_monument.pk,
                "remark": "編集済み",
            },
        )

        self.assertRedirects(response, reverse("txo:breed_detail", args=[breed.pk]))
        breed.refresh_from_db()
        self.assertEqual(breed.name, "更新した烏骨鶏")
        self.assertEqual(breed.name_kana, "こうしんしたうこっけい")
        self.assertEqual(breed.natural_monument, self.natural_monument)
        self.assertEqual(breed.remark, "編集済み")

    def test_edit_breed_allows_empty_natural_monument(self):
        """
        シナリオ:
        - 入力: 任意項目を持つ登録済みの品種と、任意項目未指定の更新後情報。
        - 処理: 品種編集フォームでメモと天然記念物区分を空欄にしてPOSTする。
        - 期待値: 品種情報が更新され、任意項目が空として保存されること。
        """
        breed = self._create_breed(name="区分解除対象")
        breed.natural_monument = self.natural_monument
        breed.remark = "解除前メモ"
        breed.save()

        response = self.client.post(
            reverse("txo:breed_edit", args=[breed.pk]),
            data={
                "species": self.species.pk,
                "name": "区分なし系統",
                "name_kana": "くぶんなしけいとう",
                "natural_monument": "",
                "remark": "",
            },
        )

        self.assertRedirects(response, reverse("txo:breed_detail", args=[breed.pk]))
        breed.refresh_from_db()
        self.assertEqual(breed.name, "区分なし系統")
        self.assertIsNone(breed.natural_monument)
        self.assertIsNone(breed.remark)

    def test_delete_breed_uses_confirm_page_and_redirects_to_list(self):
        """
        シナリオ:
        - 入力: 登録済みの品種。
        - 処理: 削除確認ページを表示し、削除フォームをPOSTする。
        - 期待値: 確認ステップを挟んだ後に品種が削除され、一覧へ戻ること。
        """
        breed = self._create_breed(name="削除対象")

        confirm_response = self.client.get(reverse("txo:breed_delete", args=[breed.pk]))
        self.assertEqual(confirm_response.status_code, 200)
        self.assertContains(confirm_response, "削除確認")
        self.assertContains(confirm_response, "削除対象")

        response = self.client.post(reverse("txo:breed_delete", args=[breed.pk]))

        self.assertRedirects(response, reverse("txo:breed_list"))
        self.assertFalse(Breed.objects.filter(pk=breed.pk).exists())

    def test_rejects_duplicate_breed_name(self):
        """
        シナリオ:
        - 入力: すでに登録済みの品種名。
        - 処理: 分類登録フォームをPOSTする。
        - 期待値: 重複エラーになり、品種が追加されないこと。
        """
        Breed.objects.create(
            name="名古屋種",
            name_kana="なごやしゅ",
            image=self._image("existing.gif"),
            species=self.species,
        )

        response = self.client.post(
            reverse("txo:breed_new"),
            data=self._base_post_data({"breed_name": "名古屋種"}),
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "alert alert-danger")
        self.assertContains(
            response, "登録できませんでした。入力内容を確認してください。"
        )
        self.assertContains(response, "text-danger")
        self.assertContains(response, "この名前の品種は登録済みです。")
        self.assertEqual(Breed.objects.filter(name="名古屋種").count(), 1)

    def _base_post_data(self, overrides=None):
        data = {
            "kingdom": self.kingdom.id,
            "phylum": self.phylum.id,
            "classification": self.classification.id,
            "family": self.family.id,
            "genus": self.genus.id,
            "species": self.species.id,
            "breed_name": "烏骨鶏",
            "breed_name_kana": "うこっけい",
            "breed_image": self._image("breed.gif"),
        }
        if overrides:
            data.update(overrides)
        return data

    def _image(self, name):
        image = (
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00"
            b"\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
        )
        return SimpleUploadedFile(name, image, content_type="image/gif")

    def _create_breed(self, name):
        return Breed.objects.create(
            name=name,
            name_kana="てすと",
            image=self._image(f"{name}.gif"),
            species=self.species,
        )
