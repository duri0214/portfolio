"""Receive the navbar request that sends the latest Apache access report."""

import logging
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from lib.apache_access.domain.service.report_service import ApacheAccessReportService
from lib.apache_access.domain.valueobject.report import (
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
    except RecipientNotConfiguredError:
        logger.error("APACHE_REPORT_RECIPIENT is not configured")
        return _redirect_to_source(request, "recipient-missing")
    except ReportRateLimitedError:
        return _redirect_to_source(request, "rate-limited")
    except ReportNotFoundError:
        logger.error("Apache access report does not exist", exc_info=True)
        return _redirect_to_source(request, "report-missing")
    except ReportStaleError:
        logger.error("Apache access report is stale", exc_info=True)
        return _redirect_to_source(request, "report-stale")
    except ReportStorageError:
        logger.error("Apache access report is unavailable", exc_info=True)
        return _redirect_to_source(request, "report-unavailable")
    except (MailSendError, ValueError, OSError):
        logger.exception("Apache access report mail failed")
        return _redirect_to_source(request, "send-failed")
    return _redirect_to_source(request, "sent")


def _redirect_to_source(request, result: str):
    """Return to the originating page with a fixed operation-result code."""
    target = request.POST.get("next", "/")
    if not url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        target = "/"

    parts = urlsplit(target)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query["apache_report"] = result
    location = urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment)
    )
    return redirect(location)
