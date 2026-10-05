"""画面とメールで共有するログ読み取り・期間集計を検証する。"""

import gzip
import zlib
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.test import SimpleTestCase

from lib.apache_access.domain.service.report_service import ApacheAccessReportService
from lib.apache_access.domain.valueobject.report import (
    ApacheAccessReportError,
    ReportNotFoundError,
    ReportReadError,
)


class ApacheAccessTrafficTests(SimpleTestCase):
    """ログの期間境界、重複排除、失敗時の扱いを確認する。"""

    def test_rotated_logs_use_local_days_and_exclusive_end(self):
        """入力: 現行・gzipログと重複パターン。処理: JSTで期間集計。期待値: 期間内だけを一度数え、識別子を返さない。"""
        start = datetime(2026, 9, 28, tzinfo=ZoneInfo("Asia/Tokyo"))
        end = datetime(2026, 10, 1, tzinfo=start.tzinfo)
        rows = (
            ("27/Sep/2026:14:59:59 +0000", 200),
            ("27/Sep/2026:15:00:00 +0000", 101),
            ("28/Sep/2026:14:59:59 +0000", 200),
            ("28/Sep/2026:15:00:00 +0000", 302),
            ("30/Sep/2026:23:59:58 +0900", 404),
            ("30/Sep/2026:23:59:59 +0900", 503),
            ("01/Oct/2026:00:00:00 +0900", 200),
            ("30/Sep/2026:12:00:00 +0900", 999),
            ("invalid timestamp", 200),
        )
        lines = [
            f'198.51.100.10 - - [{stamp}] "GET /private?token=secret HTTP/1.1" {status} 1 "-" "private-agent"\n'
            for stamp, status in rows
        ]
        with TemporaryDirectory() as directory:
            base = Path(directory)
            current = base / "access.log"
            current.write_text("".join(lines[:4]), encoding="utf-8")
            with gzip.open(base / "access.log.1.gz", "wt", encoding="utf-8") as log:
                log.write("".join(lines[4:]) + "malformed line\n")
            service = ApacheAccessReportService(
                (str(base / "access.log*"), str(current))
            )

            traffic = service.generate_traffic(start, end)

        self.assertEqual(traffic.total_requests, 5)
        self.assertEqual(traffic.responses_by_class, {1: 1, 2: 1, 3: 1, 4: 1, 5: 1})
        self.assertEqual(
            traffic.requests_by_day,
            {date(2026, 9, 28): 2, date(2026, 9, 29): 1, date(2026, 9, 30): 2},
        )
        self.assertEqual(traffic.malformed_lines, 3)
        for private_value in ("198.51.100.10", "/private", "secret", "private-agent"):
            self.assertNotIn(private_value, str(traffic))

    def test_missing_invalid_and_empty_logs_are_distinct(self):
        """入力: ログなし・解析不能・空ファイル。処理: 期間集計。期待値: 前二者は例外、空ファイルだけ0件。"""
        start = datetime(2026, 9, 28, tzinfo=ZoneInfo("Asia/Tokyo"))
        end = datetime(2026, 10, 1, tzinfo=start.tzinfo)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "access.log"
            service = ApacheAccessReportService((str(path),))
            with self.assertRaises(ReportNotFoundError):
                service.generate_traffic(start, end)
            path.write_text("unsupported format\n", encoding="utf-8")
            with self.assertRaises(ApacheAccessReportError):
                service.generate_traffic(start, end)
            path.write_text("", encoding="utf-8")

            traffic = service.generate_traffic(start, end)

        self.assertEqual(traffic.total_requests, 0)
        self.assertEqual(traffic.malformed_lines, 0)

    def test_unreadable_and_corrupt_logs_fail_without_partial_results(self):
        """入力: 読み取り拒否・破損gzip。処理: 期間集計。期待値: 読み取り例外に変換し、部分集計を成功扱いにしない。"""
        start = datetime(2026, 9, 28, tzinfo=ZoneInfo("Asia/Tokyo"))
        end = datetime(2026, 10, 1, tzinfo=start.tzinfo)
        with TemporaryDirectory() as directory:
            path = Path(directory) / "access.log"
            path.write_text("", encoding="utf-8")
            service = ApacheAccessReportService((str(Path(directory) / "access.log*"),))
            with patch("builtins.open", side_effect=PermissionError("private path")):
                with self.assertRaises(ReportReadError):
                    service.generate_traffic(start, end)
            (Path(directory) / "access.log.1.gz").write_bytes(b"not gzip")
            with self.assertRaises(ReportReadError):
                service.generate_traffic(start, end)
            with patch(
                "lib.apache_access.domain.service.access_log_aggregator.gzip.open",
                side_effect=zlib.error("corrupt deflate stream"),
            ):
                with self.assertRaises(ReportReadError):
                    service.generate_traffic(start, end)
