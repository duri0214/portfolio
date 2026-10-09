"""Apache access report library and its thin Django endpoint tests."""

import gzip
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from django.contrib.auth import get_user_model
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse

from lib.apache_access.domain.service.access_log_aggregator import (
    ApacheAccessLogAggregator,
)
from lib.apache_access.domain.service.report_mail import ApacheAccessReportMailService
from lib.apache_access.domain.service.report_service import ApacheAccessReportService
from lib.apache_access.domain.service.report_summary import (
    MAX_OUTPUT_TOKENS,
    ApacheAccessReportSummaryService,
)
from lib.apache_access.domain.valueobject.report import (
    ApacheAccessReportError,
    ApacheAccessReport,
    ApacheAccessReportSummaryError,
    ReportNotFoundError,
    ReportReadError,
    SUMMARY_INPUT_FIELDS,
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
            result = ApacheAccessLogAggregator().aggregate(
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
    def test_generate_report_keeps_only_counts_in_memory(self):
        """入力: combinedログ。処理: レポート生成。期待値: 件数だけをメモリに返す。"""
        now = datetime.now(timezone.utc).replace(microsecond=0)
        stamp = (now - timedelta(seconds=1)).strftime("%d/%b/%Y:%H:%M:%S %z")
        with TemporaryDirectory() as directory:
            base = Path(directory)
            log_path = base / "access.log"
            log_path.write_text(
                f'198.51.100.10 - - [{stamp}] "GET /?private=secret HTTP/1.1" 403 0 "-" "test"\n',
                encoding="utf-8",
            )
            service = ApacheAccessReportService((str(log_path),))
            report = service.generate_report(now)

        self.assertEqual(report.total_requests, 1)
        self.assertEqual(report.status_403, 1)
        self.assertNotIn("198.51.100.10", str(report))
        self.assertNotIn("secret", str(report))

    def test_missing_and_unparseable_logs_fail_without_writing(self):
        """入力: ログなし・異形式ログ。処理: レポート生成。期待値: 読み取りだけで失敗する。"""
        now = datetime.now(timezone.utc)
        with TemporaryDirectory() as directory:
            base = Path(directory)
            service = ApacheAccessReportService((str(base / "access.log*"),))
            with self.assertRaises(ReportNotFoundError):
                service.generate_report(now)
            (base / "access.log").write_text(
                "unsupported log format\n", encoding="utf-8"
            )
            with self.assertRaises(ApacheAccessReportError):
                service.generate_report(now)

    def test_send_uses_mail_user_as_recipient_without_persistence(self):
        """入力: combinedログと固定宛先。処理: 集計して送信。期待値: ファイルを書かない。"""
        now = datetime.now(timezone.utc).replace(microsecond=0)
        stamp = (now - timedelta(seconds=1)).strftime("%d/%b/%Y:%H:%M:%S %z")
        with TemporaryDirectory() as directory:
            base = Path(directory)
            log_path = base / "access.log"
            log_path.write_text(
                f'198.51.100.10 - - [{stamp}] "GET / HTTP/1.1" 200 1 "-" "test"\n',
                encoding="utf-8",
            )
            service = ApacheAccessReportService((str(log_path),))
            mail_service = Mock()
            mail_service.user = "admin@example.com"
            service.send_report(mail_service=mail_service, generated_at=now)

            mail_service.send_mail.assert_called_once()
            mail = mail_service.send_mail.call_args.kwargs
            self.assertEqual(mail["to"], "admin@example.com")
            self.assertIn("対象期間", mail["body"])
            self.assertIn("集計時刻", mail["html_body"])
            self.assertEqual([path.name for path in base.iterdir()], ["access.log"])

    def test_summary_failure_keeps_the_mechanical_report(self):
        """
        シナリオ:
        - 入力: GPT要約で失敗する集計サービスとcombinedログ。
        - 処理: レポートをメール送信する。
        - 期待値: GPT要約を含めず、機械的な集計メールを送信する。
        """
        now = datetime.now(timezone.utc).replace(microsecond=0)
        stamp = (now - timedelta(seconds=1)).strftime("%d/%b/%Y:%H:%M:%S %z")
        with TemporaryDirectory() as directory:
            log_path = Path(directory) / "access.log"
            log_path.write_text(
                f'198.51.100.10 - - [{stamp}] "GET / HTTP/1.1" 200 1 "-" "test"\n',
                encoding="utf-8",
            )
            service = ApacheAccessReportService((str(log_path),))
            mail_service = Mock(user="admin@example.com")
            summary_service = Mock()
            summary_service.summarize.side_effect = ApacheAccessReportSummaryError(
                "OpenAI request failed"
            )

            with self.assertLogs(
                "lib.apache_access.domain.service.report_service", level="WARNING"
            ) as logged:
                service.send_report(
                    mail_service=mail_service,
                    summary_service=summary_service,
                    generated_at=now,
                )

        mail = mail_service.send_mail.call_args.kwargs
        self.assertIn("リクエスト総数", mail["body"])
        self.assertNotIn("GPTによる参考要約", mail["body"])
        self.assertNotIn("OpenAI request failed", "\n".join(logged.output))

    def test_missing_mail_recipient_does_not_call_gpt(self):
        """
        シナリオ:
        - 入力: 宛先が未設定のメールサービスとGPT要約サービス。
        - 処理: レポートをメール送信する。
        - 期待値: メール設定エラーにし、GPT要約を呼び出さない。
        """
        now = datetime.now(timezone.utc).replace(microsecond=0)
        stamp = (now - timedelta(seconds=1)).strftime("%d/%b/%Y:%H:%M:%S %z")
        with TemporaryDirectory() as directory:
            log_path = Path(directory) / "access.log"
            log_path.write_text(
                f'198.51.100.10 - - [{stamp}] "GET / HTTP/1.1" 200 1 "-" "test"\n',
                encoding="utf-8",
            )
            service = ApacheAccessReportService((str(log_path),))
            mail_service = Mock(user="")
            summary_service = Mock()

            with self.assertRaisesRegex(ValueError, "MAIL_SMTP_USER"):
                service.send_report(
                    mail_service=mail_service,
                    summary_service=summary_service,
                    generated_at=now,
                )

        summary_service.summarize.assert_not_called()


class ApacheAccessReportSummaryTests(SimpleTestCase):
    def _report(self) -> ApacheAccessReport:
        """Return one anonymous report with representative aggregate values."""
        period_start = datetime(2026, 10, 4, tzinfo=timezone.utc)
        return ApacheAccessReport(
            period_start=period_start,
            period_end=period_start + timedelta(hours=24),
            generated_at=period_start + timedelta(hours=24),
            total_requests=100,
            status_401=3,
            status_403=2,
            status_404=5,
            status_5xx=1,
            failure_sources=4,
            top_source_failures=6,
            login_requests=8,
            top_source_login_requests=4,
            sensitive_path_successes=0,
            recent_failures=8,
            previous_failures=3,
            malformed_lines=0,
        )

    @patch("lib.apache_access.domain.service.report_summary.OpenAI")
    def test_summary_request_uses_only_allowlisted_aggregates(self, mock_openai):
        """
        シナリオ:
        - 入力: 匿名化済みの集計レポートとGPTの正常応答。
        - 処理: GPT要約を生成する。
        - 期待値: 許可リストの集計値だけを1回、出力上限付きで送信する。
        """
        mock_openai.return_value.responses.create.return_value.output_text = (
            "観測: 失敗応答は11件です。\n推測: 後半に増加した可能性があります。"
        )

        summary = ApacheAccessReportSummaryService("test-key").summarize(self._report())

        request = mock_openai.return_value.responses.create.call_args.kwargs
        payload = json.loads(request["input"])
        self.assertEqual(set(payload), set(SUMMARY_INPUT_FIELDS))
        self.assertEqual(payload["failure_response_count"], 11)
        self.assertEqual(payload["failure_response_rate"], 0.11)
        self.assertEqual(request["max_output_tokens"], MAX_OUTPUT_TOKENS)
        self.assertEqual(mock_openai.return_value.responses.create.call_count, 1)
        self.assertNotIn("198.51.100.10", request["input"])
        self.assertNotIn("token=secret", request["input"])
        self.assertEqual(
            summary,
            "観測: 失敗応答は11件です。\n推測: 後半に増加した可能性があります。",
        )

    @patch("lib.apache_access.domain.service.report_summary.OpenAI")
    def test_summary_rejects_prohibited_or_unstructured_output(self, mock_openai):
        """
        シナリオ:
        - 入力: 攻撃を断定するGPT要約。
        - 処理: GPT要約を検証する。
        - 期待値: 管理者メールへ渡さず要約エラーにする。
        """
        mock_openai.return_value.responses.create.return_value.output_text = (
            "観測: 失敗応答は11件です。\n推測: 攻撃です。"
        )

        with self.assertRaises(ApacheAccessReportSummaryError):
            ApacheAccessReportSummaryService("test-key").summarize(self._report())

    @patch.dict(
        "os.environ",
        {"APACHE_ACCESS_GPT_ENABLED": "False", "OPENAI_API_KEY": ""},
        clear=False,
    )
    def test_summary_is_disabled_without_the_feature_flag(self):
        """
        シナリオ:
        - 入力: GPT要約が無効な環境設定。
        - 処理: 要約サービスを環境変数から生成する。
        - 期待値: OpenAI APIを利用するサービスを生成しない。
        """
        self.assertIsNone(ApacheAccessReportSummaryService.from_environment())


class ApacheAccessReportMailTests(SimpleTestCase):
    def test_mail_adds_the_summary_as_escaped_reference_information(self):
        """
        シナリオ:
        - 入力: 対象期間と匿名化集計値を持つレポート、HTMLを含むGPT要約。
        - 処理: テキスト・HTMLメール本文を生成する。
        - 期待値: 根拠となる集計値のそばに参考要約を表示し、HTMLはエスケープされる。
        """
        period_start = datetime(2026, 10, 4, tzinfo=timezone.utc)
        report = ApacheAccessReport(
            period_start=period_start,
            period_end=period_start + timedelta(hours=24),
            generated_at=period_start + timedelta(hours=24),
            total_requests=20,
            status_401=0,
            status_403=0,
            status_404=2,
            status_5xx=0,
            failure_sources=1,
            top_source_failures=2,
            login_requests=0,
            top_source_login_requests=0,
            sensitive_path_successes=0,
            recent_failures=2,
            previous_failures=0,
            malformed_lines=0,
        )
        summary = "観測: 404は2件です。\n推測: <確認>が必要な可能性があります。"

        body, html_body = ApacheAccessReportMailService().build_bodies(report, summary)

        self.assertIn("対象期間", body)
        self.assertIn("GPTによる参考要約", body)
        self.assertIn(summary, body)
        self.assertIn("OpenAI APIによる参考情報", html_body)
        self.assertIn("&lt;確認&gt;", html_body)


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

    @patch(
        "lib.apache_access.report_receiver.ApacheAccessReportService.from_environment"
    )
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
        service_factory.return_value.send_report.assert_called_once()

    @patch(
        "lib.apache_access.report_receiver.ApacheAccessReportService.from_environment"
    )
    def test_operation_failures_are_visible(self, service_factory):
        """入力: ログ読み取り・SMTP失敗。処理: 管理者POST。期待値: 元画面へ失敗を通知する。"""
        self.client.force_login(self.superuser)
        cases = (
            (ReportReadError("private detail"), "report-unavailable", True),
            (MailSendError("private detail"), "send-failed", True),
        )
        for error, result, _ in cases:
            with self.subTest(result=result):
                service_factory.return_value.send_report.side_effect = error
                with self.assertLogs(
                    "lib.apache_access.report_receiver", level="ERROR"
                ):
                    response = self.client.post(
                        self.url, {"next": reverse("home:index")}
                    )
                self.assertRedirects(response, f"/?apache_report={result}")
                self.assertNotIn("private detail", response.url)

    @patch(
        "lib.apache_access.report_receiver.ApacheAccessReportService.from_environment"
    )
    def test_send_request_returns_to_the_originating_page(self, service_factory):
        """入力: 管理者の送信操作。処理: 元画面へ戻る。期待値: レポートを送信する。"""
        self.client.force_login(self.superuser)
        response = self.client.post(
            self.url,
            {"next": reverse("home:index")},
            follow=True,
        )

        self.assertRedirects(response, "/?apache_report=sent")
        service_factory.return_value.send_report.assert_called_once()

    def test_send_button_is_not_displayed_in_superuser_navbar(self):
        """入力: スーパーユーザー。処理: 共通ナビバーを表示。期待値: メール送信操作を表示しない。"""
        self.client.force_login(self.superuser)
        self.assertNotContains(
            self.client.get(reverse("home:index")), "アクセス集計をメール送信"
        )
