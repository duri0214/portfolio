import csv
from io import StringIO
from unittest.mock import Mock
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from shopping.models import StorePlanningDataSourceSnapshot


class StorePlanningDataSourceCommandTest(TestCase):
    @patch("shopping.domain.dataprovider.public_dataset.requests.get")
    def test_command_saves_public_data_source_snapshots(self, mock_get):
        """
        シナリオ:
        - 入力: e-StatデータカタログAPIと国勢調査小地域集計CSVのモックレスポンス。
        - 処理: 出店計画データソース取得コマンドを実行する。
        - 期待値: Chapter Table 周辺町丁の年代別人口がDBへ保存されること。
        """
        mock_get.side_effect = self._mock_response

        call_command("daily_fetch_store_planning_data_sources", verbosity=0)

        self.assertEqual(StorePlanningDataSourceSnapshot.objects.count(), 1)
        population = StorePlanningDataSourceSnapshot.objects.get(
            source_key="estat_population_age_groups_higashi_hokima_2"
        )
        self.assertEqual("e-Stat 国勢調査 年齢別人口", population.display_name)
        self.assertEqual("令和2年国勢調査 小地域集計", population.data_period)
        self.assertEqual(
            "東京都足立区東保木間二丁目", population.raw_data["target_area_name"]
        )
        self.assertEqual(2289, population.raw_data["total_population"])
        self.assertEqual("000009048041", population.raw_data["resource_id"])
        self.assertEqual("000032163275", population.raw_data["stat_inf_id"])
        self.assertEqual(
            {"label": "0～4歳", "population": 101},
            population.raw_data["age_groups"][0],
        )

    @patch("shopping.domain.dataprovider.public_dataset.requests.get")
    def test_command_dry_run_does_not_write_database(self, mock_get):
        """
        シナリオ:
        - 入力: dry-run指定と各公開データソースのモックレスポンス。
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
        if "getDataCatalog" in url:
            response.json.return_value = self._estat_catalog_response()
            return response
        response.text = self._estat_population_csv()
        return response

    def _estat_catalog_response(self):
        return {
            "GET_DATA_CATALOG": {
                "DATA_CATALOG_LIST_INF": {
                    "DATA_CATALOG_INF": {
                        "RESOURCES": {
                            "RESOURCE": [
                                {
                                    "@id": "000009048041",
                                    "TITLE": {
                                        "TABLE_NO": 3,
                                        "TABLE_NAME": "男女，年齢（5歳階級）別人口，平均年齢及び総年齢－町丁・字等",
                                    },
                                    "URL": "https://www.e-stat.go.jp/stat-search/file-download?&statInfId=000032163275&fileKind=1",
                                    "FORMAT": "CSV",
                                    "RELEASE_DATE": "2022-02-10",
                                    "LAST_MODIFIED_DATE": "2022-02-10",
                                }
                            ]
                        }
                    }
                }
            }
        }

    def _estat_population_csv(self):
        output = StringIO()
        writer = csv.writer(output)
        writer.writerow(["1", "令和２年国勢調査 小地域集計"])
        writer.writerow(
            ["2", "第3表 男女，年齢（5歳階級）別人口，平均年齢及び総年齢－町丁・字等"]
        )
        writer.writerow(["3"])
        writer.writerow(["4"])
        writer.writerow(
            [
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
            ]
        )
        writer.writerow(
            [
                "3399",
                "総数",
                "13121",
                "073002",
                "4",
                "",
                "",
                "",
                "東京都",
                "足立区",
                "東保木間",
                "二丁目",
                "2289",
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
            ]
        )
        return output.getvalue()
