from django.core.management import call_command
from django.test import TestCase

from taxonomy.models import (
    Breed,
    EggLedger,
    FeedGroup,
    HenGroup,
    JmaWeatherCode,
    Kingdom,
)


class SeedTaxonomyInitialDataCommandTest(TestCase):
    def test_command_creates_taxonomy_initial_data_without_fixtures(self):
        """
        シナリオ:
        - 入力: taxonomyの初期データが空のDB状態。
        - 処理: Taxonomy初期データ投入コマンドを実行する。
        - 期待値: 分類マスタ、天気コード、卵台帳の初期データが作成されること。
        """
        call_command("seed_taxonomy_initial_data", verbosity=0)

        self.assertTrue(Kingdom.objects.filter(name="動物界").exists())
        self.assertTrue(Breed.objects.filter(name="シマミミズ").exists())
        self.assertTrue(FeedGroup.objects.filter(name="初期").exists())
        self.assertTrue(HenGroup.objects.filter(name="デフォルトグループ\n").exists())
        self.assertTrue(JmaWeatherCode.objects.filter(code="100").exists())
        self.assertTrue(EggLedger.objects.exists())

    def test_command_is_idempotent(self):
        """
        シナリオ:
        - 入力: Taxonomy初期データを一度投入済みのDB状態。
        - 処理: 同じ投入コマンドを再実行する。
        - 期待値: 主キー更新として処理され、対象モデルの件数が増えないこと。
        """
        call_command("seed_taxonomy_initial_data", verbosity=0)
        breed_count = Breed.objects.count()
        weather_code_count = JmaWeatherCode.objects.count()
        egg_ledger_count = EggLedger.objects.count()

        call_command("seed_taxonomy_initial_data", verbosity=0)

        self.assertEqual(breed_count, Breed.objects.count())
        self.assertEqual(weather_code_count, JmaWeatherCode.objects.count())
        self.assertEqual(egg_ledger_count, EggLedger.objects.count())
