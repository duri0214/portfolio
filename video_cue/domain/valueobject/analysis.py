import math
from dataclasses import dataclass


class InvalidAnalysis(ValueError):
    """1件の解析 JSON が閲覧に必要な形式を満たさないことを表す。"""


def number(value: object) -> float:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise InvalidAnalysis("時刻・変化量には有限の非負数が必要です。")
    return float(value)


def file_reference(value: object, *, optional: bool = False) -> str | None:
    if optional and value is None:
        return None
    if not isinstance(value, str) or not value or "\x00" in value:
        raise InvalidAnalysis("動画の参照先が不正です。")
    return value


@dataclass(frozen=True)
class Event:
    """解析対象上の1つの動き区間とハイライト内の位置。

    Attributes:
        start: 録画内の開始秒。
        end: 録画内の終了秒。
        peak: 最大変化量（0〜1）。
        highlight_start: ハイライト内のイベント開始秒。
    """

    start: float
    end: float
    peak: float
    highlight_start: float

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass(frozen=True)
class Analysis:
    """1件の検証済み解析結果。ファイルの存在確認は Repository が担当する。

    Attributes:
        source: 解析対象のファイル名。
        duration: 解析対象の長さ（秒）。
        highlight: ハイライトの相対パス。
        events: 時刻順のイベント。
    """

    source: str
    duration: float
    highlight: str | None
    events: tuple[Event, ...]

    @classmethod
    def from_dict(cls, data: object) -> "Analysis":
        """engine の schema 2 を読み込み、不正な時刻・順序・型を拒否する。"""
        try:
            if not isinstance(data, dict):
                raise InvalidAnalysis(
                    "JSON のルートはオブジェクトである必要があります。"
                )
            version = data["schema_version"]
            if type(version) is not int or version != 2:
                raise InvalidAnalysis("未対応の schema_version です。")
            source = file_reference(data["input"]["path"])
            duration = number(data["input"]["duration_seconds"])
            highlight = file_reference(data.get("highlight_path"), optional=True)
            if not isinstance(data["events"], list):
                raise InvalidAnalysis("events は配列である必要があります。")
            events = []
            previous_end = 0.0
            previous_highlight = -1.0
            for raw in data["events"]:
                start, end = number(raw["start_seconds"]), number(raw["end_seconds"])
                peak = number(raw["peak_change_ratio"])
                offset = raw.get("highlight_start_seconds")
                offset = number(offset)
                if start < previous_end or end <= start or end > duration or peak > 1:
                    raise InvalidAnalysis("イベントの時刻・順序・変化量が不正です。")
                if highlight and offset <= previous_highlight:
                    raise InvalidAnalysis("ハイライト内の開始位置が不正です。")
                events.append(Event(start, end, peak, offset))
                previous_end = end
                previous_highlight = offset
            if bool(events) != bool(highlight):
                raise InvalidAnalysis("イベントとハイライトの指定が一致しません。")
            return cls(source, duration, highlight, tuple(events))
        except (KeyError, TypeError, OverflowError) as exc:
            raise InvalidAnalysis(
                "解析 JSON に必要な項目がないか、型が不正です。"
            ) from exc
