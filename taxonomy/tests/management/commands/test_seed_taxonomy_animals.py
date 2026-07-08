from django.core.management import call_command
from django.test import TestCase

from taxonomy.models import (
    Breed,
    Classification,
    Family,
    Genus,
    Kingdom,
    Phylum,
    Species,
)


class SeedTaxonomyAnimalsCommandTest(TestCase):
    def test_command_creates_llm_generated_animal_taxonomy_seed(self):
        """
        シナリオ:
        - 入力: taxonomyの分類データが空のDB状態。
        - 処理: LLM生成済み動物分類候補の投入コマンドを実行する。
        - 期待値: 蜂・メダカ・蚕・甲虫・家畜系の分類階層と品種相当データが作成されること。
        """
        call_command("seed_taxonomy_animals", verbosity=0)

        self.assertTrue(Kingdom.objects.filter(name="動物界").exists())
        self.assertTrue(Phylum.objects.filter(name="節足動物門").exists())
        self.assertTrue(Classification.objects.filter(name="昆虫綱").exists())
        self.assertTrue(Family.objects.filter(name="メダカ科").exists())
        self.assertTrue(Genus.objects.filter(name="ウシ属").exists())
        self.assertTrue(Species.objects.filter(name="ミナミメダカ種").exists())
        self.assertTrue(Breed.objects.filter(name="セイヨウミツバチ").exists())
        self.assertTrue(Breed.objects.filter(name="カイコ").exists())
        self.assertTrue(Breed.objects.filter(name="カブトムシ").exists())
        self.assertTrue(Breed.objects.filter(name="黒毛和種").exists())

    def test_command_is_idempotent(self):
        """
        シナリオ:
        - 入力: LLM生成済み動物分類候補を一度投入済みのDB状態。
        - 処理: 同じ投入コマンドを再実行する。
        - 期待値: species + name の重複が作られず、件数が維持されること。
        """
        call_command("seed_taxonomy_animals", verbosity=0)
        breed_count = Breed.objects.count()
        species_count = Species.objects.count()

        call_command("seed_taxonomy_animals", verbosity=0)

        self.assertEqual(breed_count, Breed.objects.count())
        self.assertEqual(species_count, Species.objects.count())
