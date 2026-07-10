from django.test import SimpleTestCase

from taxonomy.domain.valueobject.livestock_distribution import (
    build_livestock_distribution_dashboard,
)


class LivestockDistributionDashboardTest(SimpleTestCase):
    def test_build_dashboard_keeps_estat_source_metadata_and_totals(self):
        """
        シナリオ:
        - 入力: 令和6年畜産統計の採卵鶏・ブロイラー定義。
        - 処理: 畜産統計ダッシュボードを構築する。
        - 期待値: e-Statの出典、統計コード、全国羽数、都道府県数が保持されること。
        """
        dashboard = build_livestock_distribution_dashboard()

        self.assertEqual(dashboard.source_stat_code, "00500222")
        self.assertEqual(dashboard.survey_year, 2024)
        self.assertEqual(len(dashboard.categories), 2)
        self.assertEqual(dashboard.categories[0].national_birds_thousand, 170776)
        self.assertEqual(dashboard.categories[1].national_birds_thousand, 144859)
        self.assertEqual(len(dashboard.categories[0].prefectures), 47)
        self.assertEqual(len(dashboard.categories[1].prefectures), 47)

    def test_build_dashboard_does_not_estimate_secret_broiler_values(self):
        """
        シナリオ:
        - 入力: ブロイラーの都道府県別データにe-Statの秘匿値xが含まれる。
        - 処理: 畜産統計ダッシュボードを構築する。
        - 期待値: 秘匿値は推計せずNoneとして保持し、表示ラベルも秘匿扱いになること。
        """
        dashboard = build_livestock_distribution_dashboard()
        broilers = dashboard.categories[1]
        tochigi = next(
            area for area in broilers.prefectures if area.prefecture == "栃木"
        )

        self.assertEqual(tochigi.households, 8)
        self.assertIsNone(tochigi.birds_thousand)
        self.assertEqual(tochigi.birds_label, "秘匿・該当なし")
