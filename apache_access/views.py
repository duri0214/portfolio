"""環境とユーザー権限に応じてアクセス傾向を表示する。"""

import logging

from django.conf import settings
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.vary import vary_on_cookie
from django.views.generic import TemplateView

from apache_access.domain.service.dashboard import ApacheAccessDashboardService
from lib.apache_access.domain.valueobject.report import (
    ApacheAccessReportError,
    ReportNotFoundError,
    ReportReadError,
)


logger = logging.getLogger(__name__)


@method_decorator(never_cache, name="dispatch")
@method_decorator(vary_on_cookie, name="dispatch")
class IndexView(TemplateView):
    """本番のスーパーユーザーに実測集計を、それ以外にはサンプルを表示する。

    Attributes:
        template_name: アプリに属するダッシュボードのテンプレート。
        http_method_names: 読み取りのみを許可するHTTPメソッド。
    """

    template_name = "apache_access/index.html"
    http_method_names = ["get", "head", "options"]

    def get(self, request, *args, **kwargs):
        """サーバー側の環境・権限でデータ源を選び、取得失敗時は503を返す。"""
        show_real_data = (
            not settings.DEBUG
            and request.user.is_authenticated
            and request.user.is_active
            and request.user.is_superuser
        )
        context = self.get_context_data(**kwargs)
        context["show_real_data"] = show_real_data
        try:
            context["dashboard"] = (
                ApacheAccessDashboardService.build_real()
                if show_real_data
                else ApacheAccessDashboardService.build_sample()
            )
        except ApacheAccessReportError as error:
            logger.exception("Apache dashboard aggregation failed")
            if isinstance(error, ReportNotFoundError):
                message = "アクセスログが見つかりません。サーバーのログ設定を確認してください。"
            elif isinstance(error, ReportReadError):
                message = "アクセスログを読み取れません。サーバーの読み取り権限を確認してください。"
            else:
                message = "アクセスログを解析できません。ログ形式とサーバーログを確認してください。"
            context["error_message"] = message
            return self.render_to_response(context, status=503)
        return self.render_to_response(context)
