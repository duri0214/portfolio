"""実ログに依存しない、公開デモ専用の固定集計値を提供する。"""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from lib.apache_access.domain.valueobject.public_dashboard import (
    PublicAccessDashboard,
    PublicAccessResponse,
    PublicAccessWeek,
)


def build_sample_dashboard() -> PublicAccessDashboard:
    """架空の6週間を返す。環境設定・リクエスト・実ログからの入力は受け付けない。"""
    return PublicAccessDashboard(
        aggregated_at=datetime(2026, 9, 14, 9, tzinfo=ZoneInfo("Asia/Tokyo")),
        weeks=(
            PublicAccessWeek(date(2026, 8, 3), 6800),
            PublicAccessWeek(date(2026, 8, 10), 7600),
            PublicAccessWeek(date(2026, 8, 17), 7200),
            PublicAccessWeek(date(2026, 8, 24), 8600),
            PublicAccessWeek(date(2026, 8, 31), 8100),
            PublicAccessWeek(date(2026, 9, 7), 9300),
        ),
        responses=(
            PublicAccessResponse("2xx · 成功", 42000),
            PublicAccessResponse("3xx · リダイレクト", 4200),
            PublicAccessResponse("4xx · クライアントエラー", 1200),
            PublicAccessResponse("5xx · サーバーエラー", 200),
        ),
    )
