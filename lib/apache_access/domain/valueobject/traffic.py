"""ログの識別情報を含まない、期間内の通信件数。"""

from dataclasses import dataclass
from datetime import date


class ApacheAccessTrafficError(Exception):
    """Apacheアクセスログの集計に失敗したときの基底例外。"""


class TrafficNotFoundError(ApacheAccessTrafficError):
    """対象のアクセスログが見つからない。"""


class TrafficReadError(ApacheAccessTrafficError):
    """対象のアクセスログを読み取れない。"""


@dataclass(frozen=True)
class ApacheAccessTraffic:
    """任意の期間内のアクセスを日付と応答区分で集計した値。

    Attributes:
        requests_by_day (dict[date, int]): 集計開始時刻のタイムゾーンにおける日別件数。
        responses_by_class (dict[int, int]): HTTP応答区分（1〜5）別の件数。
        malformed_lines (int): 形式・日時・ステータスを解析できなかった行数。
    """

    requests_by_day: dict[date, int]
    responses_by_class: dict[int, int]
    malformed_lines: int

    @property
    def total_requests(self) -> int:
        """対象期間の応答件数の合計を返す。"""
        return sum(self.responses_by_class.values())
