"""Aggregate Apache combined access logs into identifier-free counts."""

import gzip
import re
from collections import Counter
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

from lib.apache_access.domain.valueobject.report import REPORT_FIELDS
from lib.apache_access.domain.valueobject.traffic import ApacheAccessTraffic


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

        for match, occurred_at in self._read_entries(paths, counts):
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

    def aggregate_traffic(
        self, paths: list[Path], period_start: datetime, period_end: datetime
    ) -> ApacheAccessTraffic:
        """期間の開始を含み終了を含まないログを一度読み、日別・応答区分別の件数を返す。"""
        counts = Counter()
        requests_by_day: Counter[date] = Counter()
        responses_by_class: Counter[int] = Counter()
        for match, occurred_at in self._read_entries(paths, counts):
            if not period_start <= occurred_at < period_end:
                continue
            status = int(match["status"])
            if not 100 <= status < 600:
                counts["malformed_lines"] += 1
                continue
            local_day = occurred_at.astimezone(period_start.tzinfo).date()
            requests_by_day[local_day] += 1
            responses_by_class[status // 100] += 1
        return ApacheAccessTraffic(
            requests_by_day=dict(requests_by_day),
            responses_by_class=dict(responses_by_class),
            malformed_lines=counts["malformed_lines"],
        )

    @staticmethod
    def _read_entries(
        paths: list[Path], counts: Counter[str]
    ) -> Iterator[tuple[re.Match[str], datetime]]:
        """現行・圧縮済みログを順に解析し、不正行数をcountsへ加算する内部イテレーター。"""
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
                    yield match, occurred_at
