"""アクセス傾向の表示に使う期間と集計件数。"""

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class AccessWeek:
    """1週間分のリクエスト件数。

    Attributes:
        period_start (date): 週の開始日（月曜日、JST）。
        period_end (date): 対象に含める週の最終日。進行中の週は集計日まで。
        request_count (int): 週全体のリクエスト件数。
    """

    period_start: date
    period_end: date
    request_count: int


@dataclass(frozen=True)
class AccessResponse:
    """対象期間全体のHTTP応答区分別件数。

    Attributes:
        label (str): HTTP応答区分の表示名。
        request_count (int): 区分に含まれるリクエスト件数。
    """

    label: str
    request_count: int


@dataclass(frozen=True)
class AccessDashboard:
    """サンプルまたは管理者向け実測値の画面表示に必要な集計値。

    Attributes:
        is_sample (bool): 架空の集計値であるかどうか。
        aggregated_at (datetime): 集計時刻。サンプルでは固定の設定時刻。
        weeks (tuple[AccessWeek, ...]): 週別件数を時系列順に並べた値。
        responses (tuple[AccessResponse, ...]): 対象期間全体の応答区分別件数。
        malformed_lines (int): 実測集計から除外した解析不能行数。
    """

    is_sample: bool
    aggregated_at: datetime
    weeks: tuple[AccessWeek, ...]
    responses: tuple[AccessResponse, ...]
    malformed_lines: int = 0

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
        return max((week.request_count for week in self.weeks), default=0)
