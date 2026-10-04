"""公開ダッシュボードに表示してよい期間と件数だけを保持する。"""

from dataclasses import dataclass
from datetime import date, datetime, timedelta


@dataclass(frozen=True)
class PublicAccessWeek:
    """公開用の1週間分のリクエスト件数。

    Attributes:
        period_start: 週の開始日（月曜日、JST）。
        request_count: 週全体のリクエスト件数。
    """

    period_start: date
    request_count: int

    @property
    def period_end(self) -> date:
        """対象に含む週の最終日（日曜日）を返す。"""
        return self.period_start + timedelta(days=6)


@dataclass(frozen=True)
class PublicAccessResponse:
    """対象期間全体のHTTP応答区分別件数。

    Attributes:
        label: HTTP応答区分の表示名。
        request_count: 区分に含まれるリクエスト件数。
    """

    label: str
    request_count: int


@dataclass(frozen=True)
class PublicAccessDashboard:
    """公開専用の集計値。管理者向けレポートや生ログは受け取らない。

    Attributes:
        aggregated_at: サンプルに設定した集計時刻（タイムゾーン付き）。
        weeks: 月曜日から日曜日までの週別件数を時系列順に並べた値。
        responses: 対象期間全体の応答区分別件数。
    """

    aggregated_at: datetime
    weeks: tuple[PublicAccessWeek, ...]
    responses: tuple[PublicAccessResponse, ...]

    @property
    def period_start(self) -> date:
        """対象期間の初日を返す。"""
        return self.weeks[0].period_start

    @property
    def period_end(self) -> date:
        """対象期間の最終日を返す。"""
        return self.weeks[-1].period_end

    @property
    def total_requests(self) -> int:
        """週別件数から対象期間全体のリクエスト数を求める。"""
        return sum(week.request_count for week in self.weeks)

    @property
    def peak_week_requests(self) -> int:
        """週別グラフの共通スケールに使う最大件数を返す。"""
        return max(week.request_count for week in self.weeks)
