"""公開ダッシュボードのデータ契約と非公開機能との境界を検証する。"""

import os
from dataclasses import asdict
from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase, override_settings
from django.urls import reverse

from lib.apache_access.domain.service.access_log_aggregator import (
    ApacheAccessLogAggregator,
)
from lib.apache_access.domain.service.public_dashboard import build_sample_dashboard
from lib.apache_access.domain.service.report_service import ApacheAccessReportService
from lib.apache_access.public_dashboard import apache_access_dashboard
from lib.apache_access.report_receiver import send_apache_access_report


class PublicAccessDashboardTests(SimpleTestCase):
    """集計の整合性、公開内容、入力で変更できないデータ源を検証する。"""

    def test_sample_has_consistent_periods_and_totals(self):
        """入力: 固定サンプル。処理: 期間と合計を照合。期待値: 週が連続し、両集計の合計が一致する。"""
        dashboard = build_sample_dashboard()

        self.assertEqual(dashboard.total_requests, 47600)
        self.assertEqual(
            sum(response.request_count for response in dashboard.responses),
            dashboard.total_requests,
        )
        for week in dashboard.weeks:
            self.assertEqual(week.period_start.weekday(), 0)
            self.assertGreater(week.request_count, 0)
        for earlier, later in zip(dashboard.weeks, dashboard.weeks[1:]):
            self.assertEqual(later.period_start, earlier.period_end + timedelta(days=1))
        self.assertGreater(dashboard.aggregated_at.date(), dashboard.period_end)
        self.assertEqual(dashboard.aggregated_at.utcoffset(), timedelta(hours=9))

    def test_public_data_contract_contains_only_approved_fields(self):
        """入力: 公開用集計値。処理: 全フィールドを確認。期待値: 日付・区分・件数以外が含まれない。"""
        data = asdict(build_sample_dashboard())

        self.assertEqual(set(data), {"aggregated_at", "weeks", "responses"})
        for week in data["weeks"]:
            self.assertEqual(set(week), {"period_start", "request_count"})
        for response in data["responses"]:
            self.assertEqual(set(response), {"label", "request_count"})

    def test_anonymous_dashboard_discloses_source_period_and_sample_time(self):
        """入力: 未ログインのGET。処理: 画面を描画。期待値: サンプル表示、期間、集計時刻、件数を確認できる。"""
        response = self.client.get(reverse("apache_access_dashboard"))

        self.assertTemplateUsed(response, "apache_access/dashboard.html")
        for text in (
            "この画面の数値はすべてサンプルです。",
            "公開デモ用に作成した架空の集計データ",
            "2026年8月3日",
            "2026年9月13日",
            "集計時刻（サンプル設定）",
            "2026年9月14日 09:00 JST",
            "47,600",
            "週ごとのリクエスト",
            "応答の内訳",
        ):
            self.assertContains(response, text)
        self.assertNotContains(response, "アクセス集計をメール送信")

    def test_query_and_environment_cannot_select_private_data(self):
        """入力: 実ログ設定とデータ源を指定するクエリ。処理: GET。期待値: 実集計を呼ばず固定サンプルを返す。"""
        with (
            patch.dict(
                os.environ,
                {
                    "APACHE_ACCESS_LOG_GLOBS": "/private/access.log*",
                    "APACHE_ACCESS_GPT_ENABLED": "True",
                },
            ),
            patch.object(
                ApacheAccessReportService,
                "from_environment",
                side_effect=AssertionError(
                    "公開画面から非公開サービスを呼んではならない"
                ),
            ) as private_service,
            patch.object(
                ApacheAccessLogAggregator,
                "aggregate",
                side_effect=AssertionError("公開画面で実ログを集計してはならない"),
            ) as aggregate,
        ):
            response = self.client.get(
                reverse("apache_access_dashboard"),
                {
                    "source": "real",
                    "report": "private",
                    "path": "/private/access.log",
                    "period_start": "2026-10-04",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["dashboard"], build_sample_dashboard())
        private_service.assert_not_called()
        aggregate.assert_not_called()

    def test_all_user_roles_see_only_the_sample(self):
        """入力: ゲスト・一般・スタッフ・管理者。処理: 公開GET。期待値: 権限によらず同じ架空の件数を表示する。"""
        factory = RequestFactory()
        user_model = get_user_model()
        users = (
            AnonymousUser(),
            user_model(username="viewer"),
            user_model(username="staff", is_staff=True),
            user_model(username="admin", is_staff=True, is_superuser=True),
        )
        with patch.object(
            ApacheAccessReportService, "from_environment"
        ) as private_service:
            for user in users:
                with self.subTest(user=str(user)):
                    request = factory.get(reverse("apache_access_dashboard"))
                    request.user = user
                    response = apache_access_dashboard(request)

                    self.assertContains(
                        response, "この画面の数値はすべてサンプルです。"
                    )
                    self.assertContains(response, "47,600")
        private_service.assert_not_called()

    def test_public_endpoint_is_read_only(self):
        """入力: HEADとPOST。処理: 公開URLへ送信。期待値: HEADは成功し、POSTは405で拒否する。"""
        url = reverse("apache_access_dashboard")

        self.assertEqual(self.client.head(url).status_code, 200)
        self.assertEqual(self.client.post(url).status_code, 405)

    @override_settings(DEBUG=False)
    def test_unpublished_reports_have_no_public_route(self):
        """入力: 未公開レポートのURL直指定。処理: GET。期待値: 404で、データや内部情報を返さない。"""
        for path in (
            "/apache_access/reports/",
            "/apache_access/reports/latest.json",
            "/apache_access/private/",
            "/apache_access/access.log",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 404)
                self.assertNotContains(response, "login_requests", status_code=404)

    def test_non_superusers_cannot_invoke_private_report(self):
        """入力: ゲスト・一般・スタッフのPOST。処理: 非公開URL直指定。期待値: 403で集計・送信を呼ばない。"""
        factory = RequestFactory()
        user_model = get_user_model()
        with patch.object(
            ApacheAccessReportService, "from_environment"
        ) as private_service:
            for user in (
                AnonymousUser(),
                user_model(username="viewer"),
                user_model(username="staff", is_staff=True),
            ):
                with self.subTest(user=str(user)):
                    request = factory.post(reverse("send_apache_access_report"))
                    request.user = user
                    response = send_apache_access_report(request)
                    self.assertEqual(response.status_code, 403)
        private_service.assert_not_called()

    def test_catalog_and_navigation_link_to_public_dashboard(self):
        """入力: HOMEと紹介ページ。処理: 導線を確認。期待値: 紹介と公開画面を往来でき、サンプル利用が分かる。"""
        home = self.client.get(reverse("home:index"))
        detail = self.client.get(reverse("home:about_apache_access"))

        self.assertContains(home, reverse("home:about_apache_access"))
        self.assertContains(home, reverse("apache_access_dashboard"))
        self.assertContains(detail, "すべてサンプルデータです")
        self.assertContains(
            detail,
            f'href="{reverse("apache_access_dashboard")}" class="btn btn-primary"',
        )
