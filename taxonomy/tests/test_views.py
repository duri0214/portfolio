import shutil
import tempfile

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.test import TestCase
from django.urls import reverse

from taxonomy.models import (
    Breed,
    Classification,
    Family,
    Genus,
    Kingdom,
    Phylum,
    Species,
)


class TaxonomyIndexViewTest(TestCase):
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
        self.assertContains(response, "界 > 門 > 綱 > 科 > 属 > 種")
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

        self.assertRedirects(response, reverse("txo:index"))
        breed = Breed.objects.get(name="名古屋種")
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

        self.assertRedirects(response, reverse("txo:index"))
        breed = Breed.objects.get(name="写真なし系統")
        self.assertEqual(breed.image.name, "")

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

        self.assertRedirects(response, reverse("txo:index"))
        breed = Breed.objects.select_related("species__genus").get(name="畑土系統")
        self.assertEqual(breed.species.name, "フトミミズ")
        self.assertEqual(breed.species.genus.name, "フトミミズ属")

    def test_rejects_duplicate_breed_name_in_same_species(self):
        """
        シナリオ:
        - 入力: 同じ種にすでに登録済みの品種名。
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
        self.assertContains(response, "この種には同じ名前の品種が登録済みです。")
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
