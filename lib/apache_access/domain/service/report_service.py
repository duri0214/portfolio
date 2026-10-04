"""Domain service for storing and mailing Apache access reports."""

import json
import os
import threading
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from glob import glob
from pathlib import Path

from dotenv import load_dotenv

from lib.apache_access.domain.service.access_log_aggregator import (
    aggregate_access_logs,
)
from lib.apache_access.domain.service.report_mail import build_mail_bodies
from lib.apache_access.domain.valueobject.report import (
    ApacheAccessReport,
    ApacheAccessReportError,
    RecipientNotConfiguredError,
    ReportNotFoundError,
    ReportRateLimitedError,
    ReportStaleError,
    ReportStorageError,
)
from lib.mail.mail_service import MailService

try:
    import fcntl
except ImportError:  # Windows development environment
    fcntl = None


PROJECT_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(PROJECT_ROOT / ".env")
_PROCESS_LOCK = threading.Lock()


class ApacheAccessReportService:
    """Generate, store, and mail an identifier-free Apache access report."""

    def __init__(
        self, log_globs: tuple[str, ...], report_path: Path, recipient: str = ""
    ):
        self.log_globs = log_globs
        self.report_path = report_path
        self.recipient = recipient
        self.state_path = report_path.with_suffix(".state.json")
        self.lock_path = report_path.with_suffix(".lock")

    @classmethod
    def from_environment(cls) -> "ApacheAccessReportService":
        """Create a service from the project .env used by MailService."""
        log_globs = tuple(
            value.strip()
            for value in os.getenv(
                "APACHE_ACCESS_LOG_GLOBS", "/var/log/apache2/access.log*"
            ).split(",")
            if value.strip()
        )
        default_path = PROJECT_ROOT / ".private" / "apache_access_report.json"
        report_path = Path(os.getenv("APACHE_ACCESS_REPORT_PATH", str(default_path)))
        return cls(
            log_globs=log_globs,
            report_path=report_path,
            recipient=os.getenv("APACHE_REPORT_RECIPIENT", ""),
        )

    def generate_report(
        self, generated_at: datetime | None = None
    ) -> ApacheAccessReport:
        """Aggregate the last 24 hours and atomically replace the sanitized JSON."""
        generated_at = generated_at or datetime.now(timezone.utc)
        period_end = generated_at
        period_start = period_end - timedelta(hours=24)
        paths = sorted(
            {Path(name) for pattern in self.log_globs for name in glob(pattern)}
        )
        if not paths:
            raise ReportNotFoundError(
                "Apache アクセスログが見つかりません。設定と権限を確認してください。"
            )
        try:
            counts = aggregate_access_logs(paths, period_start, period_end)
        except (OSError, EOFError) as error:
            raise ReportStorageError(
                f"Apache アクセスログを読み取れませんでした: {error}"
            ) from error
        if counts["total_requests"] == 0 and counts["malformed_lines"]:
            raise ApacheAccessReportError(
                "Apache ログ形式を解析できません。combined 形式か確認してください。"
            )

        report = ApacheAccessReport(
            period_start=period_start,
            period_end=period_end,
            generated_at=generated_at,
            **counts,
        )
        with self._locked():
            self._write_json(self.report_path, report.to_dict())
        return report

    def load_report(self) -> ApacheAccessReport:
        """Load the latest sanitized report without reading Apache logs."""
        with self._locked():
            return self._read_report()

    def send_latest_report(
        self,
        mail_service: MailService | None = None,
        sent_at: datetime | None = None,
    ) -> ApacheAccessReport:
        """Validate freshness and rate limit, then mail the latest sanitized report."""
        if not self.recipient:
            raise RecipientNotConfiguredError("宛先が設定されていません。")
        sent_at = sent_at or datetime.now(timezone.utc)

        with self._locked():
            report = self._read_report()
            if sent_at - report.generated_at > timedelta(hours=2):
                raise ReportStaleError(
                    "集計結果が古いため送信できません。定期処理を確認してください。"
                )
            last_sent_at = self._read_last_sent_at()
            if last_sent_at and sent_at - last_sent_at < timedelta(minutes=15):
                raise ReportRateLimitedError("前回の送信から15分経過していません。")

            body, html_body = build_mail_bodies(report)
            sender = mail_service or MailService()
            sender.send_mail(
                to=self.recipient,
                subject="Apache アクセス傾向レポート",
                body=body,
                html_body=html_body,
            )
            self._write_json(self.state_path, {"last_sent_at": sent_at.isoformat()})
        return report

    def _read_report(self) -> ApacheAccessReport:
        if not self.report_path.exists():
            raise ReportNotFoundError(
                "集計結果がありません。定期処理を確認してください。"
            )
        try:
            values = json.loads(self.report_path.read_text(encoding="utf-8"))
            return ApacheAccessReport.from_dict(values)
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise ReportStorageError("集計結果を読み取れませんでした。") from error

    def _read_last_sent_at(self) -> datetime | None:
        if not self.state_path.exists():
            return None
        try:
            values = json.loads(self.state_path.read_text(encoding="utf-8"))
            return datetime.fromisoformat(str(values["last_sent_at"]))
        except (OSError, ValueError, KeyError, TypeError) as error:
            raise ReportStorageError("送信状態を読み取れませんでした。") from error

    @staticmethod
    def _write_json(path: Path, values: dict[str, object]) -> None:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary_path = path.with_suffix(f"{path.suffix}.tmp")
            temporary_path.write_text(
                json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            os.replace(temporary_path, path)
        except OSError as error:
            raise ReportStorageError("集計結果を保存できませんでした。") from error

    @contextmanager
    def _locked(self):
        """Serialize report and send-state access across threads and Linux processes."""
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            with _PROCESS_LOCK, self.lock_path.open(
                "a+", encoding="utf-8"
            ) as lock_file:
                if fcntl is not None:
                    fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
                try:
                    yield
                finally:
                    if fcntl is not None:
                        fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
        except OSError as error:
            raise ReportStorageError(
                "集計結果のロックを取得できませんでした。"
            ) from error
