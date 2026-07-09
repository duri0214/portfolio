from django.core.management import call_command
from django.test import TestCase

from taxonomy.models import Breed, EggLedger, JmaWeatherCode, Kingdom


class SeedTaxonomyDataCommandTest(TestCase):
    def test_command_creates_initial_data_and_animal_taxonomy_seed(self):
        """
        シナリオ:
        - 入力: taxonomyの初期データと追加動物分類候補が空のDB状態。
        - 処理: Taxonomy統合投入コマンドを実行する。
        - 期待値: 旧fixture相当の初期データとLLM生成済み動物分類候補がどちらも作成されること。
        """
        call_command("seed_taxonomy_data", verbosity=0)

        self.assertTrue(Kingdom.objects.filter(name="動物界").exists())
        self.assertTrue(Breed.objects.filter(name="シマミミズ").exists())
        self.assertTrue(JmaWeatherCode.objects.filter(code="100").exists())
        self.assertTrue(EggLedger.objects.exists())
        self.assertTrue(Breed.objects.filter(name="セイヨウミツバチ").exists())
        self.assertTrue(Breed.objects.filter(name="黒毛和種").exists())

    def test_command_is_idempotent(self):
        """
        シナリオ:
        - 入力: Taxonomy統合投入コマンドを一度実行済みのDB状態。
        - 処理: 同じ統合投入コマンドを再実行する。
        - 期待値: 旧fixture相当データと追加動物分類候補の件数が増えないこと。
        """
        call_command("seed_taxonomy_data", verbosity=0)
        breed_count = Breed.objects.count()
        weather_code_count = JmaWeatherCode.objects.count()
        egg_ledger_count = EggLedger.objects.count()

        call_command("seed_taxonomy_data", verbosity=0)

        self.assertEqual(breed_count, Breed.objects.count())
        self.assertEqual(weather_code_count, JmaWeatherCode.objects.count())
        self.assertEqual(egg_ledger_count, EggLedger.objects.count())
