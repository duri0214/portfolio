"""Domain service for aggregating and mailing Apache access reports."""

import os
from datetime import datetime, timedelta, timezone
from glob import glob
from pathlib import Path

from dotenv import load_dotenv

from lib.apache_access.domain.service.access_log_aggregator import (
    ApacheAccessLogAggregator,
)
from lib.apache_access.domain.service.report_mail import (
    ApacheAccessReportMailService,
)
from lib.apache_access.domain.valueobject.report import (
    ApacheAccessReport,
    ApacheAccessReportError,
    ReportNotFoundError,
    ReportReadError,
)
from lib.mail.mail_service import MailService


PROJECT_ROOT = Path(__file__).resolve().parents[4]
load_dotenv(PROJECT_ROOT / ".env")


class ApacheAccessReportService:
    """Aggregate Apache logs in memory and mail the resulting report."""

    def __init__(self, log_globs: tuple[str, ...]):
        self.log_globs = log_globs

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
        return cls(log_globs=log_globs)

    def generate_report(
        self, generated_at: datetime | None = None
    ) -> ApacheAccessReport:
        """Aggregate the last 24 hours without writing a report file."""
        generated_at = generated_at or datetime.now(timezone.utc)
        period_end = generated_at
        period_start = period_end - timedelta(hours=24)
        paths = sorted(
            {Path(name) for pattern in self.log_globs for name in glob(pattern)}
        )
        if not paths:
            raise ReportNotFoundError(
                "Apache アクセスログが見つかりません。設定と読み取り権限を確認してください。"
            )
        try:
            counts = ApacheAccessLogAggregator().aggregate(
                paths, period_start, period_end
            )
        except (OSError, EOFError) as error:
            raise ReportReadError(
                f"Apache アクセスログを読み取れませんでした: {error}"
            ) from error
        if counts["total_requests"] == 0 and counts["malformed_lines"]:
            raise ApacheAccessReportError(
                "Apache ログ形式を解析できません。combined 形式か確認してください。"
            )

        return ApacheAccessReport(
            period_start=period_start,
            period_end=period_end,
            generated_at=generated_at,
            **counts,
        )

    def send_report(
        self,
        mail_service: MailService | None = None,
        generated_at: datetime | None = None,
    ) -> ApacheAccessReport:
        """Aggregate the current logs and mail the report without persistence."""
        report = self.generate_report(generated_at)
        sender = mail_service or MailService()
        recipient = getattr(sender, "user", "")
        if not recipient:
            raise ValueError("MAIL_SMTP_USER is not configured")
        body, html_body = ApacheAccessReportMailService().build_bodies(report)
        sender.send_mail(
            to=recipient,
            subject="Apache アクセス傾向レポート",
            body=body,
            html_body=html_body,
        )
        return report
