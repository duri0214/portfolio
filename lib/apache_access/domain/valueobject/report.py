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


class ApacheAccessReportError(Exception):
    """Base exception for Apache access report operations."""


class ReportNotFoundError(ApacheAccessReportError):
    """Raised when no source log is available."""


class ReportReadError(ApacheAccessReportError):
    """Raised when Apache access logs cannot be read."""


@dataclass(frozen=True)
class ApacheAccessReport:
    """Identifier-free counts for one Apache access-log period."""

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
