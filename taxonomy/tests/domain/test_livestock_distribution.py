from datetime import date
from io import StringIO

from django.test import SimpleTestCase

from taxonomy.domain.valueobject.livestock_distribution import (
    LivestockDistributionSource,
    build_livestock_distribution_dashboard_from_rows,
    load_livestock_distribution_rows,
)


class LivestockDistributionDashboardTest(SimpleTestCase):
    def test_build_dashboard_keeps_estat_source_metadata_and_totals(self):
        """
        シナリオ:
        - 入力: 令和6年畜産統計の採卵鶏・ブロイラー定義。
        - 処理: 畜産統計ダッシュボードを構築する。
        - 期待値: e-Statの出典、統計コード、全国羽数、都道府県数が保持されること。
        """
        dashboard = self._build_dashboard()

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
        dashboard = self._build_dashboard()
        broilers = dashboard.categories[1]
        tochigi = next(
            area for area in broilers.prefectures if area.prefecture == "栃木県"
        )

        self.assertEqual(tochigi.households, 8)
        self.assertIsNone(tochigi.birds_thousand)
        self.assertEqual(tochigi.birds_label, "秘匿・該当なし")

    def _build_dashboard(self):
        source = LivestockDistributionSource(
            source_name="e-Stat / 農林水産省 畜産統計調査",
            source_stat_code="00500222",
            survey_year=2024,
            retrieved_at=date(2026, 7, 11),
            source_url="https://www.e-stat.go.jp/stat-search/files",
            note="令和6年2月1日現在（畜産統計調査の調査基準日）。単位は千羽。",
        )
        rows = load_livestock_distribution_rows(StringIO(_livestock_csv()))
        return build_livestock_distribution_dashboard_from_rows(source, rows)


def _livestock_csv():
    rows = [
        "category_key,category_label,table_number,table_title,prefecture_code,prefecture,households,birds_thousand",
        "layers,採卵鶏,1,採卵鶏の飼養戸数・羽数,0,全国,2000,170776",
        "broilers,ブロイラー,2,ブロイラーの飼養戸数・羽数,0,全国,1000,144859",
    ]
    for code in range(1, 48):
        rows.append(
            f"layers,採卵鶏,1,採卵鶏の飼養戸数・羽数,{code},都道府県{code},10,100"
        )

    broiler_prefectures = ["都道府県{0}".format(code) for code in range(1, 48)]
    broiler_prefectures[8] = "栃木県"
    for code, prefecture in enumerate(broiler_prefectures, start=1):
        birds = "" if prefecture == "栃木県" else "80"
        rows.append(
            f"broilers,ブロイラー,2,ブロイラーの飼養戸数・羽数,{code},{prefecture},8,{birds}"
        )

    return "\n".join(rows)
