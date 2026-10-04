"""Aggregate Apache combined access logs into identifier-free counts."""

import gzip
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

from lib.apache_access.domain.valueobject.report import REPORT_FIELDS


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


class ApacheAccessLogAggregator:
    """Read Apache combined logs and return identifier-free counts."""

    def aggregate(
        self, paths: list[Path], period_start: datetime, period_end: datetime
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
