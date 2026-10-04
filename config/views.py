"""Project-wide operational endpoints that do not belong to a content app."""

import logging

from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.http import require_POST

from lib.apache_access.report_service import (
    ApacheAccessReportService,
    RecipientNotConfiguredError,
    ReportNotFoundError,
    ReportRateLimitedError,
    ReportStaleError,
    ReportStorageError,
)
from lib.mail.mail_service import MailSendError


logger = logging.getLogger(__name__)


@require_POST
def send_apache_access_report(request):
    """Let a superuser send the latest sanitized report to the fixed recipient."""
    if not request.user.is_authenticated or not request.user.is_superuser:
        return HttpResponseForbidden("この操作にはスーパーユーザー権限が必要です。")

    service = ApacheAccessReportService.from_environment()
    try:
        service.send_latest_report()
    except RecipientNotConfiguredError as error:
        logger.error("APACHE_REPORT_RECIPIENT is not configured")
        return _result(request, str(error), 503)
    except ReportRateLimitedError as error:
        return _result(request, str(error), 429)
    except (ReportNotFoundError, ReportStaleError, ReportStorageError) as error:
        logger.error("Apache access report is unavailable", exc_info=True)
        return _result(request, str(error), 503)
    except (MailSendError, ValueError, OSError):
        logger.exception("Apache access report mail failed")
        return _result(
            request,
            "メールを送信できませんでした。管理者ログを確認してください。",
            502,
        )
    return _result(request, "集計メールを送信しました。", 200)


def _result(request, message: str, status: int):
    """Render one operation result while preserving its HTTP status."""
    return render(
        request,
        "shared/apache_report_result.html",
        {"result": message},
        status=status,
    )
