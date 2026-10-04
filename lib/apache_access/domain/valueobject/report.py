"""Value objects and domain errors for Apache access reports."""

from dataclasses import asdict, dataclass
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
