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
from soil_analysis.domain.valueobject.estat import EstatValueRow
from soil_analysis.domain.valueobject.estat import parse_estat_datetime
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
    def test_estat_value_row_uses_category_as_period_label(self):
        """
        シナリオ:
        - 入力: 経営耕地面積規模別の VALUE レコード。
        - 処理: e-Stat VALUE レコードを保存用VOへ変換する。
        - 期待値: 地域コードではなく規模分類コードが period_label になり、分布を分類別に保存できること。
        """
        row = EstatValueRow.from_raw(
            {"@cat01": "1171", "@cat02": "1004", "@unit": "ha", "$": "250"},
            "2026-06-27",
        )

        self.assertEqual(row.period_label, "1004")
        self.assertEqual(row.value, 250)

    def test_parse_estat_datetime_makes_date_string_timezone_aware(self):
        """
        シナリオ:
        - 入力: e-Stat の更新日として返るタイムゾーンなしの日付文字列。
        - 処理: 日時文字列を Django の DateTimeField 保存用に変換する。
        - 期待値: タイムゾーン付き datetime が返り、保存時の naive datetime 警告を避けられること。
        """
        parsed = parse_estat_datetime("2025-04-09")

        self.assertIsNotNone(parsed)
        self.assertTrue(timezone.is_aware(parsed))

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
                call_command("fetch_farmland_statistics")

    @patch("soil_analysis.domain.dataprovider.estat.requests.get")
    def test_command_saves_mocked_estat_snapshot(self, mock_get):
        """
        シナリオ:
        - 入力: e-Stat API の VALUE レコードを1件返すモックレスポンス。
        - 処理: e-Stat取得コマンドを実行する。
        - 期待値: スナップショットが1件保存され、レポート集計も作成されること。
        """
        EstatDataset.objects.create(
            indicator_key="cultivated_area_distribution",
            display_name="経営耕地面積規模別面積",
            stats_data_id="000001",
            filters={"cdCat01": "1171"},
            unit="ha",
        )
        response = Mock()
        response.json.return_value = {
            "GET_STATS_DATA": {
                "RESULT_INF": {"DATE": "2026-06-27T00:00:00+09:00"},
                "STATISTICAL_DATA": {
                    "TABLE_INF": {
                        "STATISTICS_NAME_SPEC": {
                            "TABULATION_SUB_CATEGORY1": "2020年農林業センサス"
                        },
                        "SURVEY_DATE": "202001-202012",
                    },
                    "DATA_INF": {
                        "VALUE": {
                            "@cat02": "1001",
                            "@unit": "ha",
                            "$": "1000",
                        }
                    },
                },
            }
        }
        mock_get.return_value = response

        with patch.dict("os.environ", {"ESTAT_APP_ID": "fake-app-id"}):
            call_command("fetch_farmland_statistics", verbosity=0)

        self.assertEqual(AgriculturalStatisticSnapshot.objects.count(), 2)
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
                    "TABLE_INF": {
                        "STATISTICS_NAME_SPEC": {
                            "TABULATION_SUB_CATEGORY1": "2020年農林業センサス"
                        },
                        "SURVEY_DATE": "202001-202012",
                    },
                    "DATA_INF": {
                        "VALUE": {
                            "@time": "2020",
                            "@unit": "ha",
                            "$": "1000",
                        }
                    },
                }
            }
        }
        mock_get.return_value = response

        with patch.dict("os.environ", {"ESTAT_APP_ID": "fake-app-id"}):
            call_command("fetch_farmland_statistics", "--dry-run", verbosity=0)

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
        self.assertContains(response, reverse("soil:farmland_risk"))

    def test_report_view_displays_empty_state(self):
        """
        シナリオ:
        - 入力: 統計スナップショットが未保存のDB状態。
        - 処理: 離農・管理不能農地レポートを表示する。
        - 期待値: 空状態が表示され、画面が正常に表示されること。
        """
        response = self.client.get(reverse("soil:farmland_risk"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "統計データはまだ取得されていません")
        self.assertContains(response, "e-Stat地域コード 02405")
        self.assertContains(response, "データ取得状況")
        self.assertContains(response, "0002068836")
        self.assertContains(response, "https://www.e-stat.go.jp/dbview?sid=0002068836")
        self.assertContains(response, "cdCat01=1171")
        self.assertNotContains(response, "cdCat02=1001")
        self.assertContains(response, "未実装（TODO）")

    def test_report_view_displays_latest_risk_report(self):
        """
        シナリオ:
        - 入力: 六戸町の離農リスクレポートが保存済みのDB状態。
        - 処理: 離農・管理不能農地レポートを表示する。
        - 期待値: 管理不能化候補面積と10年後農地維持率が表示されること。
        """
        region = AgriculturalStatisticsService.ensure_default_configuration()
        distribution_dataset = EstatDataset.objects.get(
            indicator_key="cultivated_area_distribution"
        )
        count_dataset = EstatDataset.objects.get(
            indicator_key="cultivated_area_distribution_count"
        )
        for period_label, value in [("1001", 1000), ("1002", 100), ("1004", 250)]:
            AgriculturalStatisticSnapshot.objects.create(
                region=region,
                dataset=distribution_dataset,
                period_label=period_label,
                value=value,
                fetched_at=timezone.now(),
                estat_updated_at=timezone.now(),
                raw_data={
                    "@cat01": "1171",
                    "@cat02": period_label,
                    "$": str(value),
                    "_table_metadata": {
                        "tabulation_sub_category": "2020年農林業センサス",
                        "survey_date": "202001-202012",
                    },
                },
                source_hash=f"distribution-{period_label}",
            )
        for period_label, label, value in [
            ("1001", "計", 611),
            ("1003", "0.3ha未満", 2),
            ("1005", "0.5～1.0", 100),
        ]:
            AgriculturalStatisticSnapshot.objects.create(
                region=region,
                dataset=count_dataset,
                period_label=period_label,
                value=value,
                fetched_at=timezone.now(),
                estat_updated_at=timezone.now(),
                raw_data={
                    "@cat01": "1171",
                    "@cat02": period_label,
                    "$": str(value),
                    "_table_metadata": {
                        "tabulation_sub_category": "2020年農林業センサス",
                        "survey_date": "202001-202012",
                    },
                    "_class_metadata": {
                        "cat02": {
                            period_label: {
                                "name": label,
                                "unit": "経営体",
                            }
                        }
                    },
                },
                source_hash=f"distribution-count-{period_label}",
            )
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

        response = self.client.get(reverse("soil:farmland_risk"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "管理不能化候補面積")
        self.assertContains(response, "185")
        self.assertContains(response, "81.5")
        self.assertContains(response, "対象地域")
        self.assertContains(response, "上北郡六戸町")
        self.assertContains(response, "取得済み")
        self.assertContains(response, "データ時点")
        self.assertContains(response, "2020年農林業センサス（2020年1月〜2020年12月）")
        self.assertContains(response, "e-Stat公表/更新日")
        self.assertNotContains(response, '<th class="text-end">最新値</th>', html=True)
        self.assertNotContains(response, "アプリ取得日時")
        self.assertContains(response, "経営耕地面積規模別分布")
        self.assertContains(response, "使用した指標")
        self.assertContains(response, "使用: 経営耕地面積規模別面積（0002068836）")
        self.assertContains(response, "使用: 経営耕地面積規模別経営体数（0002068830）")
        self.assertContains(
            response,
            "面積は、各規模区分に属する経営体が持つ経営耕地面積の合計です。",
        )
        self.assertNotContains(response, "次回の e-Stat 取得バッチ後に反映されます。")
        self.assertContains(response, "計")
        self.assertContains(response, "構成比 100.0%")
        self.assertContains(response, "611 経営体")
        self.assertContains(response, "0.3ha未満")
        self.assertContains(response, "構成比 10.0%")
        self.assertContains(response, "2 経営体")
        self.assertContains(response, "0.5～1.0ha")
        self.assertContains(response, "構成比 25.0%")
        self.assertContains(response, "100 経営体")
        self.assertContains(
            response,
            "たとえば0.5〜1.0haの行は、その規模区分に属する経営体が持つ経営耕地面積を合計したhaです。",
        )
        self.assertContains(
            response,
            "経営規模区分ごとの経営体数です。面積だけでは小規模農家層の件数が分からないため、nとして併記します。",
        )
        self.assertContains(response, "未実装（TODO）")
        self.assertNotContains(response, "e-Stat スナップショット")
        self.assertNotContains(response, "<th>分類</th>", html=True)
        self.assertNotContains(response, "取得履歴トレンド")

    def test_report_view_only_lists_fetched_distribution_sources(self):
        """
        シナリオ:
        - 入力: 面積分布だけ保存済みで、経営体数分布は未取得のDB状態。
        - 処理: 離農・管理不能農地レポートを表示する。
        - 期待値: 使用した指標には実際に分布へ使った取得済み指標だけが表示されること。
        """
        region = AgriculturalStatisticsService.ensure_default_configuration()
        distribution_dataset = EstatDataset.objects.get(
            indicator_key="cultivated_area_distribution"
        )
        AgriculturalStatisticSnapshot.objects.create(
            region=region,
            dataset=distribution_dataset,
            period_label="1001",
            value=1000,
            fetched_at=timezone.now(),
            estat_updated_at=timezone.now(),
            raw_data={
                "@cat01": "1171",
                "@cat02": "1001",
                "$": "1000",
                "_table_metadata": {
                    "tabulation_sub_category": "2020年農林業センサス",
                    "survey_date": "202001-202012",
                },
            },
            source_hash="distribution-only-total",
        )
        AgriculturalRiskReport.objects.create(
            region=region,
            report_date=date(2026, 6, 27),
            total_cultivated_area=1000,
        )

        response = self.client.get(reverse("soil:farmland_risk"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "使用した指標")
        self.assertContains(response, "使用: 経営耕地面積規模別面積（0002068836）")
        self.assertNotContains(
            response, "使用: 経営耕地面積規模別経営体数（0002068830）"
        )

    def test_report_view_backfills_known_data_period_for_existing_snapshots(self):
        """
        シナリオ:
        - 入力: SURVEY_DATE 保存前の既存スナップショット。
        - 処理: 離農・管理不能農地レポートを表示する。
        - 期待値: 統計表IDから既知のデータ時点を補完して表示すること。
        """
        region = AgriculturalStatisticsService.ensure_default_configuration()
        dataset = EstatDataset.objects.get(indicator_key="cultivated_area_distribution")
        AgriculturalStatisticSnapshot.objects.create(
            region=region,
            dataset=dataset,
            period_label="1001",
            value=2354,
            fetched_at=timezone.now(),
            estat_updated_at=timezone.now(),
            raw_data={"@cat01": "1171", "@cat02": "1001", "$": "2354"},
            source_hash="legacy-total-cultivated-area-hash",
        )

        response = self.client.get(reverse("soil:farmland_risk"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "データ時点")
        self.assertContains(response, "2020年農林業センサス（2020年1月〜2020年12月）")
        self.assertNotContains(
            response, "データ時点:\n                            未取得"
        )

    def test_legacy_rokunohe_farmland_risk_url_redirects(self):
        """
        シナリオ:
        - 入力: 旧六戸町固定URLへのアクセス。
        - 処理: 離農・管理不能農地レポートを表示するURLへ遷移する。
        - 期待値: 地域固定でないURLへリダイレクトされること。
        """
        response = self.client.get(reverse("soil:rokunohe_farmland_risk"))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("soil:farmland_risk"))
