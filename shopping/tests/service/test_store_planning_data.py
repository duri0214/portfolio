from io import StringIO
from unittest.mock import Mock
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from shopping.models import StorePlanningDataSourceSnapshot


class StorePlanningDataSourceCommandTest(TestCase):
    @patch("shopping.domain.dataprovider.estat.requests.get")
    def test_command_replaces_estat_population_snapshots(self, mock_get):
        """
        シナリオ:
        - 入力: 古い保存済みスナップショットと、e-Stat国勢調査小地域集計CSVのモックレスポンス。
        - 処理: 出店計画データソース取得コマンドを実行する。
        - 期待値: 古い行が削除され、CSV内の各町丁だけがDBへ保存されること。
        """
        StorePlanningDataSourceSnapshot.objects.create(
            source_key="stale_estat_population_age_groups_99999_999999",
            display_name="古いe-Stat人口CSV集計",
            source_url="https://www.e-stat.go.jp/stat-search/files",
            status="取得済み",
            data_period="古いデータ",
            raw_data={"town_code": "999999"},
        )
        mock_get.side_effect = self._mock_response

        call_command("daily_fetch_store_planning_data_sources", verbosity=0)

        self.assertEqual(StorePlanningDataSourceSnapshot.objects.count(), 2)
        self.assertFalse(
            StorePlanningDataSourceSnapshot.objects.filter(
                source_key="stale_estat_population_age_groups_99999_999999"
            ).exists()
        )
        population = StorePlanningDataSourceSnapshot.objects.get(
            source_key="estat_population_age_groups_13121_073002"
        )
        self.assertEqual(
            "e-Stat 国勢調査 年齢別人口: 東京都足立区東保木間二丁目",
            population.display_name,
        )
        self.assertEqual("令和2年国勢調査 小地域集計", population.data_period)
        self.assertEqual(
            "東京都足立区東保木間二丁目", population.raw_data["target_area_name"]
        )
        self.assertEqual(2289, population.raw_data["total_population"])
        self.assertEqual(1120, population.raw_data["male_population"])
        self.assertEqual(1169, population.raw_data["female_population"])
        self.assertEqual(43.8, population.raw_data["average_age"])
        self.assertEqual("000009048041", population.raw_data["resource_id"])
        self.assertEqual("000032163275", population.raw_data["stat_inf_id"])
        self.assertEqual("073", population.raw_data["town_code_group"])
        self.assertEqual(
            {
                "label": "0代",
                "population": 220,
                "male_population": 110,
                "female_population": 110,
            },
            population.raw_data["age_groups"][0],
        )
        self.assertEqual(
            population.raw_data["total_population"],
            sum(row["population"] for row in population.raw_data["age_groups"]),
        )
        other_population = StorePlanningDataSourceSnapshot.objects.get(
            source_key="estat_population_age_groups_13121_073001"
        )
        self.assertEqual(1234, other_population.raw_data["total_population"])
        self.assertEqual(
            "東京都足立区東保木間一丁目",
            other_population.raw_data["target_area_name"],
        )

    @patch("shopping.domain.dataprovider.estat.requests.get")
    def test_command_dry_run_does_not_write_database(self, mock_get):
        """
        シナリオ:
        - 入力: dry-run指定とe-Stat国勢調査小地域集計CSVのモックレスポンス。
        - 処理: 出店計画データソース取得コマンドを実行する。
        - 期待値: レスポンスは取得されるがDBへ保存されないこと。
        """
        mock_get.side_effect = self._mock_response

        call_command(
            "daily_fetch_store_planning_data_sources", "--dry-run", verbosity=0
        )

        self.assertEqual(StorePlanningDataSourceSnapshot.objects.count(), 0)

    def _mock_response(self, url, **kwargs):
        response = Mock()
        response.raise_for_status.return_value = None
        response.apparent_encoding = "utf-8"
        response.text = self._estat_population_csv()
        return response

    def _estat_population_csv(self):
        output = StringIO()
        rows = [
            ["1", "令和２年国勢調査 小地域集計"],
            ["2", "第3表 男女，年齢（5歳階級）別人口，平均年齢及び総年齢－町丁・字等"],
            ["3"],
            ["4"],
            self._header_row(),
            self._population_row(
                "総数",
                "2289",
                [
                    "101",
                    "119",
                    "109",
                    "111",
                    "134",
                    "95",
                    "142",
                    "126",
                    "152",
                    "212",
                    "195",
                    "134",
                    "95",
                    "102",
                    "144",
                    "90",
                    "63",
                    "50",
                    "26",
                    "6",
                    "-",
                    "83",
                ],
                "43.8",
            ),
            self._population_row(
                "男",
                "1120",
                [
                    "52",
                    "58",
                    "55",
                    "57",
                    "66",
                    "47",
                    "70",
                    "62",
                    "74",
                    "103",
                    "95",
                    "65",
                    "47",
                    "50",
                    "70",
                    "43",
                    "30",
                    "22",
                    "12",
                    "3",
                    "-",
                    "39",
                ],
                "42.6",
            ),
            self._population_row(
                "女",
                "1169",
                [
                    "49",
                    "61",
                    "54",
                    "54",
                    "68",
                    "48",
                    "72",
                    "64",
                    "78",
                    "109",
                    "100",
                    "69",
                    "48",
                    "52",
                    "74",
                    "47",
                    "33",
                    "28",
                    "14",
                    "3",
                    "-",
                    "44",
                ],
                "45.0",
            ),
            self._population_row(
                "総数",
                "1234",
                [
                    "50",
                    "60",
                    "70",
                    "80",
                    "90",
                    "100",
                    "110",
                    "120",
                    "130",
                    "140",
                    "150",
                    "160",
                    "40",
                    "35",
                    "30",
                    "25",
                    "20",
                    "15",
                    "10",
                    "5",
                    "0",
                    "4",
                ],
                "44.1",
                town_code="073001",
                small_area_name="一丁目",
            ),
            self._population_row(
                "男",
                "600",
                [
                    "25",
                    "30",
                    "35",
                    "40",
                    "45",
                    "50",
                    "55",
                    "60",
                    "65",
                    "70",
                    "75",
                    "80",
                    "20",
                    "17",
                    "15",
                    "12",
                    "10",
                    "7",
                    "5",
                    "2",
                    "0",
                    "2",
                ],
                "43.5",
                town_code="073001",
                small_area_name="一丁目",
            ),
            self._population_row(
                "女",
                "634",
                [
                    "25",
                    "30",
                    "35",
                    "40",
                    "45",
                    "50",
                    "55",
                    "60",
                    "65",
                    "70",
                    "75",
                    "80",
                    "20",
                    "18",
                    "15",
                    "13",
                    "10",
                    "8",
                    "5",
                    "3",
                    "0",
                    "2",
                ],
                "44.8",
                town_code="073001",
                small_area_name="一丁目",
            ),
        ]
        for row in rows:
            output.write(",".join(row))
            output.write("\n")
        return output.getvalue()

    def _header_row(self):
        return [
            "5",
            "男女",
            "市区町村コード",
            "町丁字コード",
            "地域階層レベル",
            "秘匿処理",
            "秘匿先情報",
            "合算地域",
            "都道府県名",
            "市区町村名",
            "大字・町名",
            "字・丁目名",
            "総数",
            "0～4歳",
            "5～9歳",
            "10～14歳",
            "15～19歳",
            "20～24歳",
            "25～29歳",
            "30～34歳",
            "35～39歳",
            "40～44歳",
            "45～49歳",
            "50～54歳",
            "55～59歳",
            "60～64歳",
            "65～69歳",
            "70～74歳",
            "75～79歳",
            "80～84歳",
            "85～89歳",
            "90～94歳",
            "95～99歳",
            "100歳以上",
            "年齢不詳",
            "-",
            "-",
        ]

    def _population_row(
        self,
        gender: str,
        total: str,
        ages: list[str],
        average_age: str,
        town_code: str = "073002",
        small_area_name: str = "二丁目",
    ):
        return [
            "3399",
            gender,
            "13121",
            town_code,
            "4",
            "",
            "",
            "",
            "東京都",
            "足立区",
            "東保木間",
            small_area_name,
            total,
            *ages,
            "95520",
            average_age,
        ]
