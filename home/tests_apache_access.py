"""Apache ログ集計と管理者向けメール送信の境界を確認する。"""

import gzip
from datetime import timedelta
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from home.domain.service.apache_access import aggregate_access_logs
from home.models import ApacheAccessReport, ApacheReportDispatch
from lib.mail.mail_service import MailSendError


class ApacheAccessAggregationTests(SimpleTestCase):
    def test_rotated_logs_keep_only_counts(self):
        """入力: 現行・圧縮済みログ。処理: 直近24時間を集計。期待値: IP・URLを含まず件数のみ返す。"""
        now = timezone.now().replace(microsecond=0)
        stamp = now.strftime("%d/%b/%Y:%H:%M:%S %z")
        early_stamp = (now - timedelta(hours=18)).strftime("%d/%b/%Y:%H:%M:%S %z")
        with TemporaryDirectory() as directory:
            current = Path(directory) / "access.log"
            rotated = Path(directory) / "access.log.1.gz"
            current.write_text(
                f'198.51.100.10 - - [{stamp}] "GET /accounts/login/?token=secret HTTP/1.1" 401 12 "-" "test"\n'
                f'198.51.100.10 - - [{stamp}] "GET /.env?key=secret HTTP/1.1" 200 20 "-" "test"\n',
                encoding="utf-8",
            )
            with gzip.open(rotated, "wt", encoding="utf-8") as stream:
                stream.write(
                    f'198.51.100.10 - - [{stamp}] "GET /missing HTTP/1.1" 404 0 "-" "test"\n'
                    f'198.51.100.10 - - [{early_stamp}] "GET /error HTTP/1.1" 503 0 "-" "test"\n'
                )
            result = aggregate_access_logs(
                [current, rotated],
                now - timedelta(hours=24),
                now + timedelta(seconds=1),
            )

        self.assertEqual(result["total_requests"], 4)
        self.assertEqual(result["status_401"], 1)
        self.assertEqual(result["status_404"], 1)
        self.assertEqual(result["status_5xx"], 1)
        self.assertEqual(result["top_source_failures"], 3)
        self.assertEqual(result["previous_failures"], 1)
        self.assertEqual(result["recent_failures"], 2)
        self.assertEqual(result["login_requests"], 1)
        self.assertEqual(result["sensitive_path_successes"], 1)
        self.assertNotIn("198.51.100.10", str(result))
        self.assertNotIn("secret", str(result))


class ApacheAccessCommandTests(TestCase):
    def test_saves_anonymous_report(self):
        """入力: combined 形式のログ。処理: 集計コマンド。期待値: 個人情報を持たない集計行を保存する。"""
        stamp = timezone.now().strftime("%d/%b/%Y:%H:%M:%S %z")
        with TemporaryDirectory() as directory:
            log_path = Path(directory) / "access.log"
            log_path.write_text(
                f'198.51.100.10 - - [{stamp}] "GET /?private=secret HTTP/1.1" 403 0 "-" "test"\n',
                encoding="utf-8",
            )
            with override_settings(APACHE_ACCESS_LOG_GLOBS=(str(log_path),)):
                call_command("aggregate_apache_access", stdout=StringIO())

        report = ApacheAccessReport.objects.get()
        self.assertEqual(report.total_requests, 1)
        self.assertEqual(report.status_403, 1)
        self.assertTrue(ApacheReportDispatch.objects.filter(pk=1).exists())
        self.assertNotIn("198.51.100.10", str(report.__dict__))
        self.assertNotIn("secret", str(report.__dict__))

    def test_missing_or_unparseable_logs_do_not_replace_report(self):
        """入力: 読めるログがない状態と異形式ログ。処理: 集計コマンド。期待値: 失敗し保存値を更新しない。"""
        with TemporaryDirectory() as directory:
            pattern = str(Path(directory) / "access.log*")
            with override_settings(APACHE_ACCESS_LOG_GLOBS=(pattern,)):
                with self.assertRaises(CommandError):
                    call_command("aggregate_apache_access", stdout=StringIO())
                (Path(directory) / "access.log").write_text(
                    "unsupported log format\n", encoding="utf-8"
                )
                with self.assertRaises(CommandError):
                    call_command("aggregate_apache_access", stdout=StringIO())
        self.assertFalse(ApacheAccessReport.objects.exists())

    @patch("home.management.commands.aggregate_apache_access.aggregate_access_logs")
    def test_unreadable_log_reports_failure(self, aggregate):
        """入力: ログ読み取り時の権限エラー。処理: 集計コマンド。期待値: 失敗を報告し集計行を作らない。"""
        aggregate.side_effect = PermissionError("access denied")
        with TemporaryDirectory() as directory:
            log_path = Path(directory) / "access.log"
            log_path.touch()
            with override_settings(APACHE_ACCESS_LOG_GLOBS=(str(log_path),)):
                with self.assertRaisesMessage(CommandError, "access denied"):
                    call_command("aggregate_apache_access", stdout=StringIO())
        self.assertFalse(ApacheAccessReport.objects.exists())


@override_settings(APACHE_REPORT_RECIPIENT="admin@example.com")
class ApacheAccessMailTests(TestCase):
    def setUp(self):
        """各ケースに最新の匿名化集計を用意する。"""
        now = timezone.now()
        self.report = ApacheAccessReport.objects.create(
            period_start=now - timedelta(hours=24),
            period_end=now,
            generated_at=now,
            total_requests=100,
            status_401=1,
            status_403=2,
            status_404=3,
            status_5xx=4,
            failure_sources=3,
            top_source_failures=5,
            login_requests=6,
            top_source_login_requests=2,
            sensitive_path_successes=1,
            recent_failures=7,
            previous_failures=3,
            malformed_lines=0,
        )
        ApacheReportDispatch.objects.create(pk=1)
        user_model = get_user_model()
        self.superuser = user_model.objects.create_superuser(
            username="report_admin", email="admin@example.com", password="pass"
        )
        self.staff = user_model.objects.create_user(
            username="report_staff", password="pass", is_staff=True
        )
        self.url = reverse("home:send_apache_access_report")

    @patch("home.views.MailService")
    def test_permission_method_csrf_and_send_limit(self, mail_service):
        """入力: 権限別の直接アクセスと連続POST。処理: 送信URL。期待値: 管理者のCSRF付き初回のみ送信する。"""
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(self.url).status_code, 403)
        csrf_client = Client(enforce_csrf_checks=True)
        self.assertEqual(csrf_client.post(self.url).status_code, 403)
        csrf_client.force_login(self.staff)
        self.assertEqual(csrf_client.post(self.url).status_code, 403)
        csrf_client.force_login(self.superuser)
        self.assertEqual(csrf_client.get(self.url).status_code, 405)
        self.assertEqual(csrf_client.post(self.url).status_code, 403)
        csrf_client.get(reverse("home:index"))
        token = csrf_client.cookies["csrftoken"].value
        self.assertEqual(
            csrf_client.post(self.url, HTTP_X_CSRFTOKEN=token).status_code, 200
        )
        self.assertEqual(
            csrf_client.post(self.url, HTTP_X_CSRFTOKEN=token).status_code, 429
        )
        mail_service.return_value.send_mail.assert_called_once()
        mail_kwargs = mail_service.return_value.send_mail.call_args.kwargs
        self.assertEqual(mail_kwargs["to"], "admin@example.com")
        self.assertIn("対象期間", mail_kwargs["body"])
        self.assertIn("集計時刻", mail_kwargs["html_body"])

    def test_send_button_is_only_in_superuser_navbar(self):
        """入力: 一般利用者と管理者。処理: 共通ナビバーを表示。期待値: 送信操作は管理者にのみ見える。"""
        self.client.force_login(self.staff)
        self.assertNotContains(
            self.client.get(reverse("home:index")), "アクセス集計をメール送信"
        )
        self.client.force_login(self.superuser)
        self.assertContains(
            self.client.get(reverse("home:index")), "アクセス集計をメール送信"
        )

    @patch("home.views.MailService")
    def test_failed_send_can_be_retried(self, mail_service):
        """入力: SMTP失敗。処理: 管理者が連続送信。期待値: 失敗を画面に示し送信枠を消費しない。"""
        self.client.force_login(self.superuser)
        mail_service.return_value.send_mail.side_effect = MailSendError(
            "private detail"
        )
        with self.assertLogs("home.views", level="ERROR"):
            response = self.client.post(self.url)
        self.assertEqual(response.status_code, 502)
        self.assertNotContains(response, "private detail", status_code=502)
        mail_service.return_value.send_mail.side_effect = None
        self.assertEqual(self.client.post(self.url).status_code, 200)

    @patch("home.views.MailService")
    def test_stale_report_is_not_sent(self, mail_service):
        """入力: 2時間より古い集計。処理: 管理者がPOST。期待値: 送信せず再集計を促す。"""
        self.report.generated_at = timezone.now() - timedelta(hours=3)
        self.report.save(update_fields=["generated_at"])
        self.client.force_login(self.superuser)
        response = self.client.post(self.url)
        self.assertEqual(response.status_code, 503)
        mail_service.assert_not_called()
