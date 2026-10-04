"""Apache access report library and its thin Django endpoint tests."""

import gzip
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from lib.apache_access.domain.service.access_log_aggregator import (
    aggregate_access_logs,
)
from lib.apache_access.domain.service.report_service import ApacheAccessReportService
from lib.apache_access.domain.valueobject.report import (
    ApacheAccessReportError,
    RecipientNotConfiguredError,
    ReportNotFoundError,
    ReportRateLimitedError,
    ReportStaleError,
)
from lib.mail.mail_service import MailSendError


class ApacheAccessAggregationTests(SimpleTestCase):
    def test_rotated_logs_keep_only_counts(self):
        """入力: 現行・圧縮済みログ。処理: 集計。期待値: IP・URLを含まず件数だけを返す。"""
        now = datetime.now(timezone.utc).replace(microsecond=0)
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


class ApacheAccessReportServiceTests(SimpleTestCase):
    def test_generate_report_writes_only_sanitized_json(self):
        """入力: combinedログ。処理: レポート生成。期待値: JSONへ日時と件数だけを保存する。"""
        now = datetime.now(timezone.utc).replace(microsecond=0)
        stamp = (now - timedelta(seconds=1)).strftime("%d/%b/%Y:%H:%M:%S %z")
        with TemporaryDirectory() as directory:
            base = Path(directory)
            log_path = base / "access.log"
            report_path = base / "report.json"
            log_path.write_text(
                f'198.51.100.10 - - [{stamp}] "GET /?private=secret HTTP/1.1" 403 0 "-" "test"\n',
                encoding="utf-8",
            )
            service = ApacheAccessReportService((str(log_path),), report_path)
            report = service.generate_report(now)
            stored = report_path.read_text(encoding="utf-8")

        self.assertEqual(report.total_requests, 1)
        self.assertEqual(report.status_403, 1)
        self.assertNotIn("198.51.100.10", stored)
        self.assertNotIn("secret", stored)

    def test_missing_and_unparseable_logs_fail_without_report(self):
        """入力: ログなし・異形式ログ。処理: レポート生成。期待値: 失敗しJSONを作らない。"""
        now = datetime.now(timezone.utc)
        with TemporaryDirectory() as directory:
            base = Path(directory)
            report_path = base / "report.json"
            service = ApacheAccessReportService(
                (str(base / "access.log*"),), report_path
            )
            with self.assertRaises(ReportNotFoundError):
                service.generate_report(now)
            (base / "access.log").write_text(
                "unsupported log format\n", encoding="utf-8"
            )
            with self.assertRaises(ApacheAccessReportError):
                service.generate_report(now)
            self.assertFalse(report_path.exists())

    def test_send_uses_fixed_recipient_and_persists_rate_limit(self):
        """入力: 最新JSONと固定宛先。処理: 2回送信。期待値: 初回だけ送り15分以内を拒否する。"""
        now = datetime.now(timezone.utc).replace(microsecond=0)
        stamp = (now - timedelta(seconds=1)).strftime("%d/%b/%Y:%H:%M:%S %z")
        with TemporaryDirectory() as directory:
            base = Path(directory)
            log_path = base / "access.log"
            log_path.write_text(
                f'198.51.100.10 - - [{stamp}] "GET / HTTP/1.1" 200 1 "-" "test"\n',
                encoding="utf-8",
            )
            service = ApacheAccessReportService(
                (str(log_path),), base / "report.json", "admin@example.com"
            )
            service.generate_report(now)
            mail_service = Mock()
            service.send_latest_report(mail_service=mail_service, sent_at=now)
            with self.assertRaises(ReportRateLimitedError):
                service.send_latest_report(
                    mail_service=mail_service, sent_at=now + timedelta(minutes=1)
                )

            mail_service.send_mail.assert_called_once()
            mail = mail_service.send_mail.call_args.kwargs
            self.assertEqual(mail["to"], "admin@example.com")
            self.assertIn("対象期間", mail["body"])
            self.assertIn("集計時刻", mail["html_body"])
            self.assertTrue(service.state_path.exists())

    def test_recipient_and_freshness_are_required(self):
        """入力: 宛先なし・古いJSON。処理: メール送信。期待値: SMTPを呼ばず理由別に拒否する。"""
        now = datetime.now(timezone.utc).replace(microsecond=0)
        old_generated_at = now - timedelta(hours=3)
        stamp = (old_generated_at - timedelta(seconds=1)).strftime(
            "%d/%b/%Y:%H:%M:%S %z"
        )
        with TemporaryDirectory() as directory:
            base = Path(directory)
            log_path = base / "access.log"
            log_path.write_text(
                f'198.51.100.10 - - [{stamp}] "GET / HTTP/1.1" 200 1 "-" "test"\n',
                encoding="utf-8",
            )
            service = ApacheAccessReportService((str(log_path),), base / "report.json")
            with self.assertRaises(RecipientNotConfiguredError):
                service.send_latest_report(mail_service=Mock(), sent_at=now)

            service.recipient = "admin@example.com"
            service.generate_report(old_generated_at)
            mail_service = Mock()
            with self.assertRaises(ReportStaleError):
                service.send_latest_report(mail_service=mail_service, sent_at=now)
            mail_service.send_mail.assert_not_called()


class ApacheAccessReportViewTests(TestCase):
    def setUp(self):
        """入力: 管理者と一般スタッフ。処理: 各テストで送信URLを操作。期待値: 権限別に検証可能。"""
        user_model = get_user_model()
        self.superuser = user_model.objects.create_superuser(
            username="report_admin", email="admin@example.com", password="pass"
        )
        self.staff = user_model.objects.create_user(
            username="report_staff", password="pass", is_staff=True
        )
        self.url = reverse("send_apache_access_report")

    @patch("lib.apache_access.web.ApacheAccessReportService.from_environment")
    def test_permission_method_and_csrf(self, service_factory):
        """入力: 権限別アクセス。処理: 送信URL。期待値: CSRF付き管理者POSTだけ送信する。"""
        self.assertEqual(self.client.post(self.url).status_code, 403)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.post(self.url).status_code, 403)

        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.superuser)
        self.assertEqual(csrf_client.get(self.url).status_code, 405)
        self.assertEqual(csrf_client.post(self.url).status_code, 403)
        csrf_client.get(reverse("home:index"))
        token = csrf_client.cookies["csrftoken"].value
        response = csrf_client.post(
            self.url,
            {"next": reverse("home:index")},
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertRedirects(response, "/?apache_report=sent")
        service_factory.return_value.send_latest_report.assert_called_once()

    @patch("lib.apache_access.web.ApacheAccessReportService.from_environment")
    def test_operation_failures_are_visible(self, service_factory):
        """入力: 未設定・再送制限・SMTP失敗。処理: 管理者POST。期待値: 元画面へ失敗を通知する。"""
        self.client.force_login(self.superuser)
        cases = (
            (
                RecipientNotConfiguredError("宛先が設定されていません。"),
                "recipient-missing",
                True,
            ),
            (
                ReportRateLimitedError("前回の送信から15分経過していません。"),
                "rate-limited",
                False,
            ),
            (MailSendError("private detail"), "send-failed", True),
        )
        for error, result, is_logged in cases:
            with self.subTest(result=result):
                service_factory.return_value.send_latest_report.side_effect = error
                with (
                    self.assertLogs("lib.apache_access.web", level="ERROR")
                    if is_logged
                    else nullcontext()
                ):
                    response = self.client.post(
                        self.url, {"next": reverse("home:index")}
                    )
                self.assertRedirects(response, f"/?apache_report={result}")
                self.assertNotIn("private detail", response.url)

    @patch("lib.apache_access.web.ApacheAccessReportService.from_environment")
    def test_result_is_a_notice_on_the_originating_page(self, service_factory):
        """入力: 管理者の送信操作。処理: 元画面へ戻る。期待値: 専用画面を作らず結果を通知する。"""
        self.client.force_login(self.superuser)
        response = self.client.post(
            self.url,
            {"next": reverse("home:index")},
            follow=True,
        )

        self.assertRedirects(response, "/?apache_report=sent")
        self.assertContains(response, "集計メールを送信しました。")
        service_factory.return_value.send_latest_report.assert_called_once()

    def test_send_button_is_only_in_superuser_navbar(self):
        """入力: 一般スタッフと管理者。処理: 共通ナビバー表示。期待値: 操作は管理者にだけ見える。"""
        self.client.force_login(self.staff)
        self.assertNotContains(
            self.client.get(reverse("home:index")), "アクセス集計をメール送信"
        )
        self.client.force_login(self.superuser)
        self.assertContains(
            self.client.get(reverse("home:index")), "アクセス集計をメール送信"
        )
