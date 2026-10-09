"""サンプルまたは共通ライブラリの実測集計を画面用に整える。"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from apache_access.domain.valueobject.dashboard import (
    AccessDashboard,
    AccessResponse,
    AccessWeek,
)
from lib.apache_access.domain.service.traffic_service import ApacheAccessTrafficService


JST = ZoneInfo("Asia/Tokyo")
RESPONSE_LABELS = (
    (1, "1xx · 情報"),
    (2, "2xx · 成功"),
    (3, "3xx · リダイレクト"),
    (4, "4xx · クライアントエラー"),
    (5, "5xx · サーバーエラー"),
)


class ApacheAccessDashboardService:
    """週別グラフと期間全体の応答区分を構築する。"""

    @staticmethod
    def build_sample() -> AccessDashboard:
        """実ログ・環境設定に依存しない架空の6週間を返す。"""
        start = date(2026, 8, 3)
        counts = (6800, 7600, 7200, 8600, 8100, 9300)
        responses = {2: 42000, 3: 4200, 4: 1200, 5: 200}
        return AccessDashboard(
            is_sample=True,
            aggregated_at=datetime(2026, 9, 14, 9, tzinfo=JST),
            weeks=tuple(
                AccessWeek(
                    period_start=start + timedelta(weeks=index),
                    period_end=start + timedelta(weeks=index, days=6),
                    request_count=count,
                )
                for index, count in enumerate(counts)
            ),
            responses=tuple(
                AccessResponse(label, responses[code])
                for code, label in RESPONSE_LABELS
                if code in responses
            ),
        )

    @staticmethod
    def build_real(aggregated_at: datetime | None = None) -> AccessDashboard:
        """今週を含む6週間をlibで集計し、識別情報を含まない表示用の値にする。"""
        aggregated_at = (aggregated_at or datetime.now(JST)).astimezone(JST)
        today = aggregated_at.date()
        this_monday = today - timedelta(days=today.weekday())
        first_monday = this_monday - timedelta(weeks=5)
        period_start = datetime.combine(first_monday, time.min, tzinfo=JST)
        traffic = ApacheAccessTrafficService.from_environment().generate(
            period_start, aggregated_at
        )
        weeks = []
        for index in range(6):
            start = first_monday + timedelta(weeks=index)
            end = min(start + timedelta(days=6), today)
            count = sum(
                count
                for day, count in traffic.requests_by_day.items()
                if start <= day <= end
            )
            weeks.append(AccessWeek(start, end, count))
        return AccessDashboard(
            is_sample=False,
            aggregated_at=aggregated_at,
            weeks=tuple(weeks),
            responses=tuple(
                AccessResponse(label, traffic.responses_by_class.get(code, 0))
                for code, label in RESPONSE_LABELS
                if code != 1 or traffic.responses_by_class.get(1, 0)
            ),
            malformed_lines=traffic.malformed_lines,
        )
