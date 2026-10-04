"""Value objects and domain errors for Apache access reports."""

from dataclasses import dataclass
from datetime import datetime


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

SUMMARY_INPUT_FIELDS = (
    "period_start",
    "period_end",
    "request_count",
    "failure_response_count",
    "failure_response_rate",
    "status_401_count",
    "status_403_count",
    "status_404_count",
    "status_5xx_count",
    "failed_source_count",
    "max_failed_response_count_per_source",
    "login_request_count",
    "max_login_request_count_per_source",
    "sensitive_path_success_count",
    "first_half_failure_count",
    "second_half_failure_count",
    "failure_count_change",
    "malformed_line_count",
)


class ApacheAccessReportError(Exception):
    """Base exception for Apache access report operations."""


class ReportNotFoundError(ApacheAccessReportError):
    """Raised when no source log is available."""


class ReportReadError(ApacheAccessReportError):
    """Raised when Apache access logs cannot be read."""


class ApacheAccessReportSummaryError(ApacheAccessReportError):
    """Raised when an optional GPT summary cannot be used."""


@dataclass(frozen=True)
class ApacheAccessReport:
    """Identifier-free counts for one Apache access-log period.

    Attributes:
        period_start: 集計対象期間の開始時刻。
        period_end: 集計対象期間の終了時刻。
        generated_at: レポートを生成した時刻。
        total_requests: 対象期間のリクエスト総数。
        status_401: 401応答の件数。
        status_403: 403応答の件数。
        status_404: 404応答の件数。
        status_5xx: 5xx応答の件数。
        failure_sources: 失敗応答を返した送信元の匿名化件数。
        top_source_failures: 一つの送信元に集中した失敗応答の最大件数。
        login_requests: ログイン先へのリクエスト件数。
        top_source_login_requests: 一つの送信元からのログイン先リクエスト最大件数。
        sensitive_path_successes: 要注意パス候補へ2xxを返した件数。
        recent_failures: 対象期間後半の失敗応答件数。
        previous_failures: 対象期間前半の失敗応答件数。
        malformed_lines: 解析できなかったログ行数。
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

    def summary_input(self) -> dict[str, str | int | float]:
        """Return only the explicitly allowlisted aggregates for GPT."""
        failure_response_count = (
            self.status_401 + self.status_403 + self.status_404 + self.status_5xx
        )
        failure_response_rate = (
            round(failure_response_count / self.total_requests, 4)
            if self.total_requests
            else 0.0
        )
        values: dict[str, str | int | float] = {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "request_count": self.total_requests,
            "failure_response_count": failure_response_count,
            "failure_response_rate": failure_response_rate,
            "status_401_count": self.status_401,
            "status_403_count": self.status_403,
            "status_404_count": self.status_404,
            "status_5xx_count": self.status_5xx,
            "failed_source_count": self.failure_sources,
            "max_failed_response_count_per_source": self.top_source_failures,
            "login_request_count": self.login_requests,
            "max_login_request_count_per_source": self.top_source_login_requests,
            "sensitive_path_success_count": self.sensitive_path_successes,
            "first_half_failure_count": self.previous_failures,
            "second_half_failure_count": self.recent_failures,
            "failure_count_change": self.recent_failures - self.previous_failures,
            "malformed_line_count": self.malformed_lines,
        }
        return {field: values[field] for field in SUMMARY_INPUT_FIELDS}
