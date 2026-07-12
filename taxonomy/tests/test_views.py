import shutil
import tempfile
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.test import SimpleTestCase
from django.test import TestCase
from django.urls import reverse

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
        self.assertNotContains(response, "e-Stat 畜産統計による鶏の地域別飼養分布")
        self.assertNotContains(response, "livestock-prefecture-map")

    def test_observation_page_shows_livestock_distribution_upload_form(self):
        """
        シナリオ:
        - 入力: 畜産統計CSVが未登録のDB状態。
        - 処理: 鶏の観察グラフページを表示する。
        - 期待値: 初回データ取得フォームと、空の日本地図用コンテナが表示されること。
        """
        response = self.client.get(reverse("txo:observation"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "畜産統計データ取得")
        self.assertContains(response, "畜産統計CSVが未登録です。")
        self.assertContains(response, 'name="csv_file"')
        self.assertContains(response, "disabled")
        self.assertContains(response, "畜産統計CSV未登録")
        self.assertContains(response, "livestock-distribution-data")
        self.assertContains(response, "livestock-prefecture-map")
        self.assertContains(response, "e-Stat畜産統計データを取得")

    def test_observation_page_displays_livestock_distribution_dashboard(self):
        """
        シナリオ:
        - 入力: 畜産統計CSVが登録済みのDB状態。
        - 処理: 鶏の観察グラフページを表示する。
        - 期待値: e-Stat畜産統計の採卵鶏・ブロイラー可視化に必要なメタ情報とJSONが表示されること。
        """
        self._create_livestock_dataset()

        response = self.client.get(reverse("txo:observation"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "e-Stat 畜産統計による鶏の地域別飼養分布")
        self.assertContains(response, "政府統計コード 00500222")
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

    def test_superuser_can_upload_livestock_distribution_dataset(self):
        """
        シナリオ:
        - 入力: スーパーユーザーと畜産統計CSV登録フォームのPOSTデータ。
        - 処理: 鶏の観察グラフページへCSVをPOSTする。
        - 期待値: データセットが作成され、観察ページで畜産統計ダッシュボードが表示されること。
        """
        user = get_user_model().objects.create_superuser(
            username="taxonomy_admin",
            email="taxonomy_admin@example.com",
            password="password",
        )
        self.client.force_login(user)

        response = self.client.post(
            reverse("txo:observation"),
            data=self._livestock_dataset_post_data(),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(LivestockDistributionDataset.objects.count(), 1)
        self.assertContains(response, "畜産統計データを取得しました。")
        self.assertContains(response, "e-Stat 畜産統計による鶏の地域別飼養分布")

    def test_rejects_livestock_distribution_upload_without_permission(self):
        """
        シナリオ:
        - 入力: 未ログインユーザーと畜産統計CSV登録フォームのPOSTデータ。
        - 処理: 鶏の観察グラフページへCSVをPOSTする。
        - 期待値: データセットは作成されず、権限エラーが表示されること。
        """
        response = self.client.post(
            reverse("txo:observation"),
            data=self._livestock_dataset_post_data(),
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(LivestockDistributionDataset.objects.count(), 0)
        self.assertContains(response, "畜産統計データを取得する権限がありません。")

    def _create_livestock_dataset(self):
        return LivestockDistributionDataset.objects.create(
            title="令和6年畜産統計",
            csv_file=SimpleUploadedFile(
                "livestock.csv",
                _livestock_distribution_csv().encode("utf-8"),
                content_type="text/csv",
            ),
            source_name="e-Stat / 農林水産省 畜産統計調査",
            source_stat_code="00500222",
            survey_year=2024,
            retrieved_at="2026-07-11",
            source_url="https://www.e-stat.go.jp/stat-search/files",
            note=(
                "令和6年2月1日現在。単位は千羽。e-Statの秘匿値 x と"
                "該当なし - は推計せず秘匿・該当なしとして表示します。"
            ),
        )

    def _livestock_dataset_post_data(self):
        return {
            "title": "令和6年畜産統計",
            "csv_file": SimpleUploadedFile(
                "livestock.csv",
                _livestock_distribution_csv().encode("utf-8"),
                content_type="text/csv",
            ),
            "source_name": "e-Stat / 農林水産省 畜産統計調査",
            "source_stat_code": "00500222",
            "survey_year": "2024",
            "retrieved_at": "2026-07-11",
            "source_url": "https://www.e-stat.go.jp/stat-search/files",
            "note": (
                "令和6年2月1日現在。単位は千羽。e-Statの秘匿値 x と"
                "該当なし - は推計せず秘匿・該当なしとして表示します。"
            ),
            "is_active": "on",
        }


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
