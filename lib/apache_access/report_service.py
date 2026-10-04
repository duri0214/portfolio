"""Command-line entry point for sending an Apache access report."""

from lib.apache_access.domain.service.report_service import ApacheAccessReportService
from lib.apache_access.domain.valueobject.report import ApacheAccessReportError
from lib.mail.mail_service import MailSendError


def main() -> int:
    """Aggregate and send one report, returning a shell exit code."""
    try:
        ApacheAccessReportService.from_environment().send_report()
    except (ApacheAccessReportError, MailSendError, ValueError) as error:
        print(error)
        return 1
    print("Apache アクセス集計メールを送信しました。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
