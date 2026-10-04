"""Command-line entry point for generating an Apache access report."""

from lib.apache_access.domain.service.report_service import ApacheAccessReportService
from lib.apache_access.domain.valueobject.report import ApacheAccessReportError


def main() -> int:
    """Generate one sanitized report for manual execution and return a shell exit code."""
    try:
        ApacheAccessReportService.from_environment().generate_report()
    except ApacheAccessReportError as error:
        print(error)
        return 1
    print("Apache アクセス集計を保存しました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
