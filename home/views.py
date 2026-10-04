"""HOME 画面、カタログ詳細、管理者向け集計メールのビューを定義する。"""

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.http import HttpResponseForbidden
from django.shortcuts import render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import TemplateView

from home.domain.repository.apache_access import (
    ApacheAccessReportRepository,
    ApacheReportDispatchRepository,
)
from home.domain.valueobject.catalog import Catalog
from lib.mail.mail_service import MailSendError, MailService


logger = logging.getLogger(__name__)


@require_POST
def send_apache_access_report(request):
    """スーパーユーザーが最新の匿名化集計だけを固定宛先へ送る。"""
    if not request.user.is_authenticated or not request.user.is_superuser:
        return HttpResponseForbidden("この操作にはスーパーユーザー権限が必要です。")
    if not settings.APACHE_REPORT_RECIPIENT:
        logger.error("APACHE_REPORT_RECIPIENT is not configured")
        return render(
            request,
            "home/apache_report_result.html",
            {"result": "宛先が設定されていません。"},
            status=503,
        )

    report = ApacheAccessReportRepository.latest()
    if report is None:
        return render(
            request,
            "home/apache_report_result.html",
            {"result": "集計結果がありません。定期処理を確認してください。"},
            status=503,
        )
    if timezone.now() - report.generated_at > timedelta(hours=2):
        return render(
            request,
            "home/apache_report_result.html",
            {
                "result": "集計結果が古いため送信できません。定期処理を確認してください。"
            },
            status=503,
        )

    try:
        with transaction.atomic():
            dispatch = ApacheReportDispatchRepository.locked_state()
            now = timezone.now()
            if dispatch.last_sent_at and now - dispatch.last_sent_at < timedelta(
                minutes=15
            ):
                return render(
                    request,
                    "home/apache_report_result.html",
                    {"result": "前回の送信から15分経過していません。"},
                    status=429,
                )
            context = {"report": report}
            sent = MailService().send_mail(
                to=settings.APACHE_REPORT_RECIPIENT,
                subject="Apache アクセス傾向レポート",
                body=render_to_string("home/email/apache_report.txt", context),
                html_body=render_to_string("home/email/apache_report.html", context),
            )
            if not sent:
                raise MailSendError("MailService returned False")
            dispatch.last_sent_at = now
            dispatch.save(update_fields=["last_sent_at"])
    except (MailSendError, ValueError, OSError):
        logger.exception("Apache access report mail failed")
        return render(
            request,
            "home/apache_report_result.html",
            {"result": "メールを送信できませんでした。管理者ログを確認してください。"},
            status=502,
        )

    return render(
        request,
        "home/apache_report_result.html",
        {"result": "集計メールを送信しました。"},
    )


class CatalogContextMixin:
    """カタログをテンプレート表示用の値に変換する。"""

    def _catalog_for_display(self, catalog: Catalog) -> Catalog:
        """URLを解決したカタログを返す。"""
        app_url = (
            reverse(catalog.app_url_name)
            if catalog.app_url_name
            else catalog.external_url
        )
        return catalog.with_urls(
            detail_url=reverse(f"home:{catalog.detail_url_name}"),
            app_url=app_url,
        )


class IndexView(CatalogContextMixin, TemplateView):
    """全カタログを表示するHOME画面のビュー。"""

    template_name = "home/index.html"

    def get_context_data(self, **kwargs):
        """全カタログを含むテンプレートコンテキストを返す。"""
        context = super().get_context_data(**kwargs)
        context["catalogs"] = [
            self._catalog_for_display(catalog) for catalog in Catalog.all()
        ]
        return context


class CatalogDetailView(CatalogContextMixin, TemplateView):
    """指定したカタログの詳細画面を表示するビュー。

    Attributes:
        catalog_slug: 表示対象のカタログを識別するスラッグ。
    """

    catalog_slug = None

    def get_context_data(self, **kwargs):
        """対象カタログを含むテンプレートコンテキストを返す。"""
        context = super().get_context_data(**kwargs)
        context["catalog"] = self._catalog_for_display(Catalog.get(self.catalog_slug))
        return context
