"""Apache access logs are aggregated and mailed without retaining identifiers."""

import gzip
import json
import os
import re
import threading
from collections import Counter
from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from glob import glob
from html import escape
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

from lib.mail.mail_service import MailService

try:
    import fcntl
except ImportError:  # Windows development environment
    fcntl = None


PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

ACCESS_LINE = re.compile(
    r'^(?P<source>\S+) \S+ \S+ \[(?P<time>[^]]+)\] "(?P<request>[^"]*)" (?P<status>\d{3}) \S+(?: .*)?$'
)
LOGIN_PATHS = {"/accounts/login/", "/admin/login/"}
SENSITIVE_PATHS = {
    "/.env",
    "/.git/config",
    "/wp-admin/",
    "/wp-login.php",
    "/phpmyadmin/",
}
REPORT_FIELDS = (
    "total_requests",
    "status_401",
    "status_403",
    "status_404",
    "status_5xx",
    "failure_sources",
    "top_source_failures",
    "login_requests",
    "top_source_login_requests",
    "sensitive_path_successes",
    "recent_failures",
    "previous_failures",
    "malformed_lines",
)
TOKYO = ZoneInfo("Asia/Tokyo")
_PROCESS_LOCK = threading.Lock()


class ApacheAccessReportError(Exception):
    """Base exception for Apache access report operations."""


class ReportNotFoundError(ApacheAccessReportError):
    """Raised when a source log or sanitized report is unavailable."""


class ReportStaleError(ApacheAccessReportError):
    """Raised when the sanitized report is too old to send."""


class ReportRateLimitedError(ApacheAccessReportError):
    """Raised when a report was sent within the last 15 minutes."""


class RecipientNotConfiguredError(ApacheAccessReportError):
    """Raised when the fixed administrator recipient is absent."""


class ReportStorageError(ApacheAccessReportError):
    """Raised when a sanitized report or state file cannot be handled."""


@dataclass(frozen=True)
class ApacheAccessReport:
    """Identifier-free counts for one Apache access-log period.

    Attributes:
        period_start: Start of the aggregation period.
        period_end: End of the aggregation period.
        generated_at: Time the report was generated.
        total_requests: Total request count.
        status_401: Count of 401 responses.
        status_403: Count of 403 responses.
        status_404: Count of 404 responses.
        status_5xx: Count of 5xx responses.
        failure_sources: Number of sources that received failure responses.
        top_source_failures: Largest failure count concentrated on one source.
        login_requests: Requests to portfolio login paths.
        top_source_login_requests: Largest login request count from one source.
        sensitive_path_successes: Successful responses to sensitive path candidates.
        recent_failures: Failure count in the second half of the period.
        previous_failures: Failure count in the first half of the period.
        malformed_lines: Log lines that could not be parsed.
    """

    period_start: datetime
    period_end: datetime
    generated_at: datetime
    total_requests: int
    status_401: int
    status_403: int
    status_404: int
    status_5xx: int
    failure_sources: int
    top_source_failures: int
    login_requests: int
    top_source_login_requests: int
    sensitive_path_successes: int
    recent_failures: int
    previous_failures: int
    malformed_lines: int

    def to_dict(self) -> dict[str, str | int]:
        """Return a JSON-safe dictionary containing only dates and counts."""
        values = asdict(self)
        for field_name in ("period_start", "period_end", "generated_at"):
            values[field_name] = values[field_name].isoformat()
        return values

    @classmethod
    def from_dict(cls, values: dict[str, object]) -> "ApacheAccessReport":
        """Restore a report from the identifier-free JSON representation."""
        dates = {
            field_name: datetime.fromisoformat(str(values[field_name]))
            for field_name in ("period_start", "period_end", "generated_at")
        }
        counts = {field_name: int(values[field_name]) for field_name in REPORT_FIELDS}
        return cls(**dates, **counts)


def aggregate_access_logs(
    paths: list[Path], period_start: datetime, period_end: datetime
) -> dict[str, int]:
    """Read combined logs and return counts after discarding source and URL values."""
    counts = Counter()
    failures_by_source = Counter()
    logins_by_source = Counter()
    midpoint = period_start + (period_end - period_start) / 2

    for path in paths:
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8", errors="replace") as log_file:
            for line in log_file:
                match = ACCESS_LINE.match(line)
                if match is None:
                    counts["malformed_lines"] += 1
                    continue
                try:
                    occurred_at = datetime.strptime(
                        match["time"], "%d/%b/%Y:%H:%M:%S %z"
                    )
                except ValueError:
                    counts["malformed_lines"] += 1
                    continue
                if not period_start <= occurred_at < period_end:
                    continue

                counts["total_requests"] += 1
                status = int(match["status"])
                if status in (401, 403, 404):
                    counts[f"status_{status}"] += 1
                elif status >= 500:
                    counts["status_5xx"] += 1

                if status in (401, 403, 404) or status >= 500:
                    failures_by_source[match["source"]] += 1
                    half = (
                        "recent_failures"
                        if occurred_at >= midpoint
                        else "previous_failures"
                    )
                    counts[half] += 1

                request_parts = match["request"].split(" ", 2)
                if len(request_parts) < 2:
                    counts["malformed_lines"] += 1
                    continue
                path_only = unquote(urlsplit(request_parts[1]).path).lower()
                if path_only in LOGIN_PATHS:
                    counts["login_requests"] += 1
                    logins_by_source[match["source"]] += 1
                if 200 <= status < 300 and path_only in SENSITIVE_PATHS:
                    counts["sensitive_path_successes"] += 1

    counts["failure_sources"] = len(failures_by_source)
    counts["top_source_failures"] = max(failures_by_source.values(), default=0)
    counts["top_source_login_requests"] = max(logins_by_source.values(), default=0)
    return {field_name: counts[field_name] for field_name in REPORT_FIELDS}


class ApacheAccessReportService:
    """Generate, store, and mail an identifier-free Apache access report.

    Attributes:
        log_globs: Absolute glob patterns for current and rotated access logs.
        report_path: JSON file shared by the batch user and Web process.
        recipient: Fixed administrator email recipient.
    """

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

            body, html_body = self._mail_bodies(report)
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

    @staticmethod
    def _mail_bodies(report: ApacheAccessReport) -> tuple[str, str]:
        period_start = report.period_start.astimezone(TOKYO).strftime(
            "%Y-%m-%d %H:%M JST"
        )
        period_end = report.period_end.astimezone(TOKYO).strftime("%Y-%m-%d %H:%M JST")
        generated_at = report.generated_at.astimezone(TOKYO).strftime(
            "%Y-%m-%d %H:%M JST"
        )
        rows = (
            ("リクエスト総数", report.total_requests),
            ("401", report.status_401),
            ("403", report.status_403),
            ("404", report.status_404),
            ("5xx", report.status_5xx),
            ("失敗応答の送信元数", report.failure_sources),
            ("一つの送信元に集中した失敗応答の最大件数", report.top_source_failures),
            ("ログイン先へのリクエスト", report.login_requests),
            (
                "一つの送信元からのログイン先リクエストの最大件数",
                report.top_source_login_requests,
            ),
            ("要注意パス候補への 2xx", report.sensitive_path_successes),
            ("失敗応答（期間前半）", report.previous_failures),
            ("失敗応答（期間後半）", report.recent_failures),
            ("解析できなかったログ行数", report.malformed_lines),
        )
        text_rows = "\n".join(f"{label}: {value}" for label, value in rows)
        body = (
            "Apache アクセス傾向レポート\n"
            f"対象期間: {period_start} ～ {period_end}\n"
            f"集計時刻: {generated_at}\n\n"
            f"{text_rows}\n\n"
            "これらの数値は調査のきっかけであり、攻撃や情報漏えいを確定するものではありません。"
        )
        html_rows = "".join(
            f"<tr><td>{escape(label)}</td><td>{value}</td></tr>"
            for label, value in rows
        )
        html_body = (
            '<!doctype html><html lang="ja"><body>'
            "<h1>Apache アクセス傾向レポート</h1>"
            f"<p>対象期間: {escape(period_start)} ～ {escape(period_end)}<br>"
            f"集計時刻: {escape(generated_at)}</p>"
            f'<table border="1" cellpadding="6">{html_rows}</table>'
            "<p>これらの数値は調査のきっかけであり、攻撃や情報漏えいを確定するものではありません。</p>"
            "</body></html>"
        )
        return body, html_body


def main() -> int:
    """Generate one sanitized report for cron and return a shell exit code."""
    try:
        ApacheAccessReportService.from_environment().generate_report()
    except ApacheAccessReportError as error:
        print(error)
        return 1
    print("Apache アクセス集計を保存しました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
