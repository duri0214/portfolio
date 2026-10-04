"""アプリの表示と、本番の管理者に限定した実測データの境界を検証する。"""

import os
from dataclasses import asdict, replace
from datetime import date, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AnonymousUser
from django.contrib.staticfiles import finders
from django.test import (
    Client,
    RequestFactory,
    SimpleTestCase,
    TestCase,
    override_settings,
)
from django.urls import reverse

from apache_access.domain.service.dashboard import ApacheAccessDashboardService
from apache_access.domain.valueobject.dashboard import AccessResponse, AccessWeek
from apache_access.views import IndexView
from lib.apache_access.domain.service.report_service import ApacheAccessReportService
from lib.apache_access.domain.valueobject.report import (
    ApacheAccessReportError,
    ReportNotFoundError,
    ReportReadError,
)
from lib.apache_access.report_receiver import send_apache_access_report


def real_dashboard_fixture():
    """権限とキャッシュのテストでサンプルと区別できる実測値を作る。"""
    return replace(
        ApacheAccessDashboardService.build_sample(),
        is_sample=False,
        weeks=(AccessWeek(date(2026, 9, 7), date(2026, 9, 13), 321),),
        responses=(AccessResponse("2xx · 成功", 321),),
    )


class DashboardDataTests(SimpleTestCase):
    """サンプルの契約と、ライブラリ集計から画面への変換を検証する。"""

    def test_sample_has_consistent_periods_and_totals(self):
        """入力: 固定サンプル。処理: 期間と合計を照合。期待値: 週が連続し、両集計の合計が一致する。"""
        dashboard = ApacheAccessDashboardService.build_sample()

        self.assertTrue(dashboard.is_sample)
        self.assertEqual(dashboard.total_requests, 47600)
        self.assertEqual(sum(row.request_count for row in dashboard.responses), 47600)
        for week in dashboard.weeks:
            self.assertEqual(week.period_start.weekday(), 0)
            self.assertEqual(week.period_end, week.period_start + timedelta(days=6))
        for earlier, later in zip(dashboard.weeks, dashboard.weeks[1:]):
            self.assertEqual(later.period_start, earlier.period_end + timedelta(days=1))
        self.assertGreater(dashboard.aggregated_at.date(), dashboard.period_end)
        self.assertEqual(dashboard.aggregated_at.utcoffset(), timedelta(hours=9))

    def test_display_contract_excludes_private_report_fields(self):
        """入力: 表示用集計値。処理: 全フィールドを確認。期待値: 生ログと管理者メール専用の情報が含まれない。"""
        data = asdict(ApacheAccessDashboardService.build_sample())

        self.assertEqual(
            set(data),
            {"is_sample", "aggregated_at", "weeks", "responses", "malformed_lines"},
        )
        for week in data["weeks"]:
            self.assertEqual(set(week), {"period_start", "period_end", "request_count"})
        for response in data["responses"]:
            self.assertEqual(set(response), {"label", "request_count"})

    def test_real_data_uses_six_weeks_through_the_aggregation_time(self):
        """入力: 期間内外の実ログ形式の行。処理: 実測表示の構築。期待値: 今週の途中までを集計し、識別子を渡さない。"""
        now = datetime(2026, 10, 1, 12, tzinfo=ZoneInfo("Asia/Tokyo"))
        with TemporaryDirectory() as directory:
            path = Path(directory) / "access.log"
            path.write_text(
                '198.51.100.1 - - [24/Aug/2026:00:00:00 +0900] "GET /private?token=secret HTTP/1.1" 200 1 "-" "private-agent"\n'
                '198.51.100.1 - - [01/Oct/2026:11:59:59 +0900] "GET /private HTTP/1.1" 503 1 "-" "private-agent"\n'
                '198.51.100.1 - - [01/Oct/2026:12:00:00 +0900] "GET /private HTTP/1.1" 404 1 "-" "private-agent"\n',
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"APACHE_ACCESS_LOG_GLOBS": str(path)}):
                dashboard = ApacheAccessDashboardService.build_real(now)

        self.assertFalse(dashboard.is_sample)
        self.assertEqual(len(dashboard.weeks), 6)
        self.assertEqual(dashboard.period_start, date(2026, 8, 24))
        self.assertEqual(dashboard.period_end, date(2026, 10, 1))
        self.assertEqual(dashboard.aggregated_at, now)
        self.assertEqual(dashboard.total_requests, 2)
        self.assertEqual(
            [row.request_count for row in dashboard.responses], [1, 0, 0, 1]
        )
        self.assertEqual(
            [row.request_count for row in dashboard.weeks], [1, 0, 0, 0, 0, 1]
        )
        for private_value in ("198.51.100.1", "/private", "secret", "private-agent"):
            self.assertNotIn(private_value, str(dashboard))


class DashboardViewTests(SimpleTestCase):
    """環境・権限・失敗時表示とアプリの導線を検証する。"""

    def test_app_renders_sample_with_its_own_template_and_favicon(self):
        """入力: 未ログインのGET。処理: 描画。期待値: アプリ専用テンプレートとfavicon、サンプルの出典と期間が表示される。"""
        response = self.client.get(reverse("apache_access:index"))

        self.assertTemplateUsed(response, "apache_access/index.html")
        self.assertTemplateUsed(response, "apache_access/base.html")
        self.assertTemplateNotUsed(response, "home/base.html")
        self.assertTrue(finders.find("apache_access/c_a.ico"))
        for text in (
            "この画面の数値はすべてサンプルです。",
            "公開デモ用に作成した架空の集計データ",
            "2026年8月3日",
            "2026年9月13日",
            "集計時刻（サンプル設定）",
            "2026年9月14日 09:00 JST",
            "47,600",
            'href="/static/apache_access/c_a.ico"',
        ):
            self.assertContains(response, text)
        self.assertNotContains(response, 'aria-label="breadcrumb"')
        self.assertNotContains(response, "アクセス集計をメール送信")
        home = self.client.get(reverse("home:index"))
        self.assertContains(home, 'href="/static/home/c_h.ico"')

    def test_only_production_active_superusers_receive_real_data(self):
        """入力: 開発/本番とゲスト/一般/スタッフ/管理者/無効管理者。処理: GET。期待値: 本番の有効な管理者だけ実集計する。"""
        user_model = get_user_model()
        users = (
            AnonymousUser(),
            user_model(username="viewer"),
            user_model(username="staff", is_staff=True),
            user_model(username="admin", is_staff=True, is_superuser=True),
            user_model(username="inactive", is_superuser=True, is_active=False),
        )
        for debug in (True, False):
            for user in users:
                with (
                    self.subTest(debug=debug, user=str(user)),
                    override_settings(DEBUG=debug),
                    patch.object(
                        ApacheAccessDashboardService,
                        "build_real",
                        return_value=real_dashboard_fixture(),
                    ) as real,
                ):
                    request = RequestFactory().get(reverse("apache_access:index"))
                    request.user = user
                    response = IndexView.as_view()(request).render()
                    expected_real = not debug and user.is_active and user.is_superuser
                    self.assertEqual(
                        response.context_data["show_real_data"], expected_real
                    )
                    self.assertEqual(real.call_count, int(expected_real))
                    if expected_real:
                        self.assertContains(
                            response, "実測データを表示しています（管理者限定）。"
                        )
                        self.assertNotContains(response, "サンプル")
                    else:
                        self.assertContains(
                            response, "この画面の数値はすべてサンプルです。"
                        )
                        self.assertNotContains(response, "321")
                    self.assertIn("no-store", response["Cache-Control"])
                    self.assertIn("private", response["Cache-Control"])
                    self.assertIn("Cookie", response["Vary"])

    @override_settings(DEBUG=False)
    def test_query_and_environment_cannot_grant_access_to_real_data(self):
        """入力: ゲストと実測を要求するURL/環境設定。処理: GET。期待値: 実集計に接続せずサンプルを返す。"""
        with (
            patch.dict(os.environ, {"APACHE_ACCESS_LOG_GLOBS": "/private/access.log*"}),
            patch.object(
                ApacheAccessReportService, "from_environment"
            ) as report_service,
        ):
            response = self.client.get(
                reverse("apache_access:index"),
                {
                    "source": "real",
                    "is_superuser": "true",
                    "debug": "false",
                    "path": "/private/access.log",
                },
                secure=True,
            )
        self.assertEqual(
            response.context["dashboard"], ApacheAccessDashboardService.build_sample()
        )
        report_service.assert_not_called()

    @override_settings(DEBUG=False)
    def test_log_failures_return_503_without_details_or_sample_fallback(self):
        """入力: 本番管理者とログ欠損/読み取り/解析エラー。処理: GET。期待値: 詳細を含めず503を表示し、偽の0件やサンプルにしない。"""
        for error, message in (
            (
                ReportNotFoundError("/private/access.log"),
                "アクセスログが見つかりません",
            ),
            (ReportReadError("private credentials"), "アクセスログを読み取れません"),
            (
                ApacheAccessReportError("private raw line"),
                "アクセスログを解析できません",
            ),
        ):
            with (
                self.subTest(error=type(error).__name__),
                patch.object(
                    ApacheAccessDashboardService, "build_real", side_effect=error
                ),
                self.assertLogs("apache_access.views", level="ERROR"),
            ):
                request = RequestFactory().get(reverse("apache_access:index"))
                request.user = get_user_model()(is_superuser=True)
                response = IndexView.as_view()(request).render()
            self.assertContains(response, message, status_code=503)
            self.assertNotContains(response, str(error), status_code=503)
            self.assertNotContains(response, "サンプル", status_code=503)
            self.assertNotContains(response, "総リクエスト数", status_code=503)
            self.assertIn("no-store", response["Cache-Control"])

    @override_settings(DEBUG=False)
    def test_empty_readable_logs_show_zero_and_do_not_send_mail(self):
        """入力: 本番管理者と空の読み取り可能ログ。処理: GET。期待値: 実測0件を表示し、メールとGPTを呼ばない。"""
        with TemporaryDirectory() as directory:
            path = Path(directory) / "access.log"
            path.write_text("", encoding="utf-8")
            with (
                patch.dict(os.environ, {"APACHE_ACCESS_LOG_GLOBS": str(path)}),
                patch.object(ApacheAccessReportService, "send_report") as send_report,
                patch(
                    "lib.apache_access.domain.service.report_service.ApacheAccessReportSummaryService"
                ) as gpt,
            ):
                request = RequestFactory().get(reverse("apache_access:index"))
                request.user = get_user_model()(is_superuser=True)
                response = IndexView.as_view()(request).render()
        self.assertContains(
            response, "対象ログ内に、対象期間のリクエストはありません。"
        )
        self.assertEqual(response.context_data["dashboard"].total_requests, 0)
        self.assertNotContains(response, "width: %")
        self.assertContains(response, "width: 0%")
        send_report.assert_not_called()
        gpt.assert_not_called()

    def test_public_endpoint_is_read_only(self):
        """入力: HEADとPOST。処理: アプリURLへ送信。期待値: HEADは成功し、POSTは405で拒否する。"""
        url = reverse("apache_access:index")
        self.assertEqual(self.client.head(url).status_code, 200)
        self.assertEqual(self.client.post(url).status_code, 405)

    @override_settings(DEBUG=False)
    def test_unpublished_reports_have_no_public_route(self):
        """入力: 未公開レポートのURL直指定。処理: GET。期待値: 404でデータを返さない。"""
        for path in (
            "/apache_access/reports/",
            "/apache_access/reports/latest.json",
            "/apache_access/private/",
            "/apache_access/access.log",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path, secure=True).status_code, 404)

    def test_non_superusers_cannot_invoke_private_report(self):
        """入力: ゲスト・一般・スタッフのPOST。処理: 送信URL直指定。期待値: 403で集計・送信を呼ばない。"""
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
                    request = RequestFactory().post(
                        reverse("send_apache_access_report")
                    )
                    request.user = user
                    self.assertEqual(
                        send_apache_access_report(request).status_code, 403
                    )
        private_service.assert_not_called()

    def test_catalog_and_navigation_link_to_app(self):
        """入力: HOMEと紹介ページ。処理: 導線を確認。期待値: 名前空間付きのアプリURLと公開デモの説明が表示される。"""
        home = self.client.get(reverse("home:index"))
        detail = self.client.get(reverse("home:about_apache_access"))
        self.assertContains(home, reverse("home:about_apache_access"))
        self.assertContains(home, reverse("apache_access:index"))
        self.assertContains(detail, "公開デモはサンプルデータです")
        self.assertContains(detail, 'href="/apache_access/" class="btn btn-primary"')


@override_settings(
    DEBUG=False,
    CACHES={"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}},
    MIDDLEWARE=[
        "django.middleware.cache.UpdateCacheMiddleware",
        *settings.MIDDLEWARE,
        "django.middleware.cache.FetchFromCacheMiddleware",
    ],
)
class DashboardSessionTests(TestCase):
    """セッションが変わっても管理者の実測値が共有されないことを検証する。"""

    def test_logout_and_guest_requests_never_receive_cached_real_values(self):
        """入力: キャッシュ有効下の本番管理者とゲスト。処理: 管理者GET→ゲストGET→ログアウトGET。期待値: 実測値は管理者の1回のみ。"""
        admin = get_user_model().objects.create_user(
            username="dashboard_admin", is_superuser=True, is_staff=True
        )
        self.client.force_login(admin)
        url = reverse("apache_access:index")
        with patch.object(
            ApacheAccessDashboardService,
            "build_real",
            return_value=real_dashboard_fixture(),
        ) as real:
            admin_response = self.client.get(url, secure=True)
            guest_response = Client().get(url, secure=True)
            self.client.logout()
            logout_response = self.client.get(url, secure=True)

        self.assertContains(
            admin_response, "実測データを表示しています（管理者限定）。"
        )
        self.assertContains(admin_response, "321")
        for response in (guest_response, logout_response):
            self.assertContains(response, "47,600")
            self.assertNotContains(response, "321")
            self.assertTrue(response.context["dashboard"].is_sample)
        real.assert_called_once()
