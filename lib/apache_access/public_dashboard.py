"""公開用の固定サンプル集計を表示するHTTP入口。"""

from django.shortcuts import render
from django.views.decorators.http import require_safe

from lib.apache_access.domain.service.public_dashboard import build_sample_dashboard


@require_safe
def apache_access_dashboard(request):
    """すべての閲覧者に同じサンプルを表示し、非公開集計には接続しない。"""
    return render(
        request,
        "apache_access/dashboard.html",
        {"dashboard": build_sample_dashboard()},
    )
