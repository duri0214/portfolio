from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase

from shopping.models import StorePlanningDataSourceSnapshot


class StorePlanningDataSourceCommandTest(TestCase):
    @patch("shopping.domain.dataprovider.public_dataset.requests.get")
    def test_command_saves_public_data_source_snapshots(self, mock_get):
        """
        シナリオ:
        - 入力: 警察庁ページ、jSTAT MAPページのモックレスポンス。
        - 処理: 出店計画データソース取得コマンドを実行する。
        - 期待値: 2種類のデータソース取得結果がDBへ保存されること。
        """
        mock_get.side_effect = self._mock_response

        call_command("daily_fetch_store_planning_data_sources", verbosity=0)

        self.assertEqual(StorePlanningDataSourceSnapshot.objects.count(), 2)

        accident = StorePlanningDataSourceSnapshot.objects.get(
            source_key="npa_traffic_accident"
        )
        self.assertEqual("2019年から2024年", accident.data_period)
        self.assertIn("2024", accident.raw_data["years"])

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
        if "npa.go.jp" in url:
            response.text = """
                <a href="/publications/statistics/koutsuu/opendata/2019/opendata_2019.html">2019年</a>
                <a href="/publications/statistics/koutsuu/opendata/2024/opendata_2024.html">2024年</a>
            """
            return response
        response.text = "<html><head><title>jSTAT MAP</title></head></html>"
        return response
