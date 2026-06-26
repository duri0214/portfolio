from datetime import date
from unittest.mock import Mock, patch

from django.core.management import CommandError, call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from soil_analysis.domain.dataprovider.estat import EstatApiClient
from soil_analysis.domain.repository.agricultural_statistics import (
    AgriculturalStatisticsRepository,
)
from soil_analysis.domain.service.agricultural_statistics import (
    AgriculturalRiskCalculator,
    AgriculturalStatisticsService,
)
from soil_analysis.domain.valueobject.estat import AgriculturalRiskInput
from soil_analysis.models import (
    AgriculturalRegion,
    AgriculturalRiskReport,
    AgriculturalStatisticSnapshot,
    EstatDataset,
)


class EstatApiClientTest(TestCase):
    @patch("soil_analysis.domain.dataprovider.estat.requests.get")
    def test_get_stats_data_passes_app_id_area_and_filters(self, mock_get):
        """
        シナリオ:
        - 入力: appId、統計表ID、地域コード、カテゴリフィルタ。
        - 処理: e-Stat API クライアントで統計値を取得する。
        - 期待値: appId、statsDataId、cdArea、フィルタがクエリパラメータに含まれること。
        """
        response = Mock()
        response.json.return_value = {"GET_STATS_DATA": {}}
        mock_get.return_value = response

        client = EstatApiClient("fake-app-id")
        data = client.get_stats_data("000001", "02405", {"cdCat01": "A"})

        self.assertEqual(data, {"GET_STATS_DATA": {}})
        called_params = mock_get.call_args.kwargs["params"]
        self.assertEqual(called_params["appId"], "fake-app-id")
        self.assertEqual(called_params["statsDataId"], "000001")
        self.assertEqual(called_params["cdArea"], "02405")
        self.assertEqual(called_params["cdCat01"], "A")
        self.assertEqual(called_params["metaGetFlg"], "Y")


class AgriculturalStatisticsRepositoryTest(TestCase):
    def test_save_snapshot_does_not_duplicate_same_source_hash(self):
        """
        シナリオ:
        - 入力: 同じ地域、指標、期間、source_hash の統計値を2回保存する。
        - 処理: Repositoryでスナップショット保存を実行する。
        - 期待値: DB上のスナップショットは1件だけになり、2回目は既存扱いになること。
        """
        region = AgriculturalRegion.objects.create(
            area_code="02405", name="上北郡六戸町", prefecture_name="青森県"
        )
        dataset = EstatDataset.objects.create(
            indicator_key="total_cultivated_area",
            display_name="経営耕地面積",
            stats_data_id="000001",
            unit="ha",
        )
        fetched_at = timezone.now()

        _, first_created = AgriculturalStatisticsRepository.save_snapshot(
            region=region,
            dataset=dataset,
            period_label="2020",
            value=1000,
            fetched_at=fetched_at,
            estat_updated_at=None,
            raw_data={"$": "1000"},
            source_hash="same-hash",
        )
        _, second_created = AgriculturalStatisticsRepository.save_snapshot(
            region=region,
            dataset=dataset,
            period_label="2020",
            value=1000,
            fetched_at=fetched_at,
            estat_updated_at=None,
            raw_data={"$": "1000"},
            source_hash="same-hash",
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(AgriculturalStatisticSnapshot.objects.count(), 1)

    def test_save_snapshot_keeps_changed_source_hash_as_trend(self):
        """
        シナリオ:
        - 入力: 同じ地域、指標、期間で source_hash だけ異なる統計値。
        - 処理: Repositoryでスナップショット保存を実行する。
        - 期待値: 値の変化履歴として2件のスナップショットが保存されること。
        """
        region = AgriculturalRegion.objects.create(
            area_code="02405", name="上北郡六戸町", prefecture_name="青森県"
        )
        dataset = EstatDataset.objects.create(
            indicator_key="age_70_plus_area",
            display_name="70歳以上面積",
            stats_data_id="000002",
            unit="ha",
        )
        fetched_at = timezone.now()

        for value, source_hash in [(300, "hash-1"), (320, "hash-2")]:
            AgriculturalStatisticsRepository.save_snapshot(
                region=region,
                dataset=dataset,
                period_label="2020",
                value=value,
                fetched_at=fetched_at,
                estat_updated_at=None,
                raw_data={"$": str(value)},
                source_hash=source_hash,
            )

        self.assertEqual(AgriculturalStatisticSnapshot.objects.count(), 2)

    def test_ensure_dataset_updates_placeholder_stats_data_id(self):
        """
        シナリオ:
        - 入力: 統計表IDが TODO のまま作成済みの指標定義。
        - 処理: Repositoryで初期指標定義の存在を保証する。
        - 期待値: ユーザー設定済みの値ではなく TODO の場合だけ、確認済みの初期値に更新されること。
        """
        EstatDataset.objects.create(
            indicator_key="total_cultivated_area",
            display_name="経営耕地面積",
            stats_data_id="TODO_TOTAL_CULTIVATED_AREA",
            filters={},
            unit="ha",
        )

        dataset = AgriculturalStatisticsRepository.ensure_dataset(
            {
                "indicator_key": "total_cultivated_area",
                "display_name": "経営耕地面積",
                "stats_data_id": "0002068836",
                "filters": {
                    "cdCat01": "1171",
                    "cdCat02": "1001",
                },
                "unit": "ha",
                "category": "base",
            }
        )

        self.assertEqual(dataset.stats_data_id, "0002068836")
        self.assertEqual(dataset.filters["cdCat01"], "1171")


class AgriculturalRiskCalculatorTest(TestCase):
    def test_calculate_uses_issue_formula(self):
        """
        シナリオ:
        - 入力: 総面積1000ha、70歳以上300ha、60代200ha、後継者なし50%。
        - 処理: 離農リスク計算を実行する。
        - 期待値: Issue記載の式どおり、確定候補150ha、予備軍35ha、維持率81.5%になること。
        """
        result = AgriculturalRiskCalculator.calculate(
            AgriculturalRiskInput(
                total_cultivated_area=1000,
                age_70_plus_area=300,
                age_60s_area=200,
                no_successor_ratio=0.5,
                shrink_stop_intention_ratio=0.25,
            )
        )

        self.assertEqual(result.aging_risk, 30.0)
        self.assertEqual(result.succession_risk, 50.0)
        self.assertEqual(result.intention_risk, 25.0)
        self.assertEqual(result.retirement_confirmed_area, 150.0)
        self.assertEqual(result.retirement_reserve_area, 35.0)
        self.assertEqual(result.unmanageable_candidate_area, 185.0)
        self.assertEqual(result.farmland_maintenance_rate, 81.5)

    def test_calculate_returns_none_for_missing_inputs(self):
        """
        シナリオ:
        - 入力: 後継者なし割合が未取得の統計値。
        - 処理: 離農リスク計算を実行する。
        - 期待値: 計算できない候補面積は None になり、欠損を画面で判別できること。
        """
        result = AgriculturalRiskCalculator.calculate(
            AgriculturalRiskInput(
                total_cultivated_area=1000,
                age_70_plus_area=300,
                age_60s_area=200,
                no_successor_ratio=None,
                shrink_stop_intention_ratio=0.25,
            )
        )

        self.assertIsNone(result.retirement_confirmed_area)
        self.assertIsNone(result.unmanageable_candidate_area)


class AgriculturalStatisticsCommandTest(TestCase):
    def test_command_requires_estat_app_id(self):
        """
        シナリオ:
        - 入力: ESTAT_APP_ID が未設定の環境。
        - 処理: e-Stat取得コマンドを実行する。
        - 期待値: API呼び出し前に CommandError が発生すること。
        """
        with patch.dict("os.environ", {"ESTAT_APP_ID": ""}):
            with self.assertRaises(CommandError):
                call_command("fetch_rokunohe_farmland_statistics")

    @patch("soil_analysis.domain.dataprovider.estat.requests.get")
    def test_command_saves_mocked_estat_snapshot(self, mock_get):
        """
        シナリオ:
        - 入力: e-Stat API の VALUE レコードを1件返すモックレスポンス。
        - 処理: e-Stat取得コマンドを実行する。
        - 期待値: スナップショットが1件保存され、レポート集計も作成されること。
        """
        EstatDataset.objects.create(
            indicator_key="total_cultivated_area",
            display_name="経営耕地面積",
            stats_data_id="000001",
            unit="ha",
        )
        response = Mock()
        response.json.return_value = {
            "GET_STATS_DATA": {
                "RESULT_INF": {"DATE": "2026-06-27T00:00:00+09:00"},
                "STATISTICAL_DATA": {
                    "DATA_INF": {
                        "VALUE": {
                            "@time": "2020",
                            "@unit": "ha",
                            "$": "1000",
                        }
                    }
                },
            }
        }
        mock_get.return_value = response

        with patch.dict("os.environ", {"ESTAT_APP_ID": "fake-app-id"}):
            call_command("fetch_rokunohe_farmland_statistics", verbosity=0)

        self.assertEqual(AgriculturalStatisticSnapshot.objects.count(), 1)
        self.assertEqual(AgriculturalRiskReport.objects.count(), 1)

    @patch("soil_analysis.domain.dataprovider.estat.requests.get")
    def test_command_dry_run_does_not_write_database(self, mock_get):
        """
        シナリオ:
        - 入力: dry-run 指定と e-Stat API の VALUE レコード。
        - 処理: e-Stat取得コマンドを実行する。
        - 期待値: APIレスポンスは解析されるが、DBにはスナップショットが保存されないこと。
        """
        EstatDataset.objects.create(
            indicator_key="total_cultivated_area",
            display_name="経営耕地面積",
            stats_data_id="000001",
            unit="ha",
        )
        response = Mock()
        response.json.return_value = {
            "GET_STATS_DATA": {
                "STATISTICAL_DATA": {
                    "DATA_INF": {
                        "VALUE": {
                            "@time": "2020",
                            "@unit": "ha",
                            "$": "1000",
                        }
                    }
                }
            }
        }
        mock_get.return_value = response

        with patch.dict("os.environ", {"ESTAT_APP_ID": "fake-app-id"}):
            call_command("fetch_rokunohe_farmland_statistics", "--dry-run", verbosity=0)

        self.assertEqual(AgriculturalStatisticSnapshot.objects.count(), 0)
        self.assertEqual(AgriculturalRiskReport.objects.count(), 0)


class AgriculturalRiskReportViewTest(TestCase):
    def test_home_displays_farmland_risk_report_button(self):
        """
        シナリオ:
        - 入力: soil_analysis ホーム画面へのアクセス。
        - 処理: ホーム画面を表示する。
        - 期待値: 離農・管理不能農地レポートへの導線が表示されること。
        """
        response = self.client.get(reverse("soil:home"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "離農・管理不能農地レポート")
        self.assertContains(response, reverse("soil:rokunohe_farmland_risk"))

    def test_report_view_displays_empty_state(self):
        """
        シナリオ:
        - 入力: 統計スナップショットが未保存のDB状態。
        - 処理: 離農・管理不能農地レポートを表示する。
        - 期待値: 空状態が表示され、画面が正常に表示されること。
        """
        response = self.client.get(reverse("soil:rokunohe_farmland_risk"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "統計データはまだ取得されていません")
        self.assertContains(response, "e-Stat地域コード 02405")

    def test_report_view_displays_latest_risk_report(self):
        """
        シナリオ:
        - 入力: 六戸町の離農リスクレポートが保存済みのDB状態。
        - 処理: 離農・管理不能農地レポートを表示する。
        - 期待値: 管理不能化候補面積と10年後農地維持率が表示されること。
        """
        region = AgriculturalStatisticsService.ensure_default_configuration()
        AgriculturalRiskReport.objects.create(
            region=region,
            report_date=date(2026, 6, 27),
            total_cultivated_area=1000,
            age_70_plus_area=300,
            age_60s_area=200,
            no_successor_ratio=0.5,
            shrink_stop_intention_ratio=0.25,
            aging_risk=30,
            succession_risk=50,
            intention_risk=25,
            retirement_confirmed_area=150,
            retirement_reserve_area=35,
            unmanageable_candidate_area=185,
            farmland_maintenance_rate=81.5,
        )

        response = self.client.get(reverse("soil:rokunohe_farmland_risk"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "管理不能化候補面積")
        self.assertContains(response, "185")
        self.assertContains(response, "81.5")
