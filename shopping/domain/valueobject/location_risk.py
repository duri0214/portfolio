from dataclasses import dataclass


@dataclass(frozen=True)
class EntryRateScenario:
    """
    店前通行量から期待来店数を見積もるための入店率シナリオ。

    Attributes:
        label: 画面に表示するシナリオ名。
        rate_percent: 店前を通った人のうち入店すると仮定する割合。
    """

    label: str
    rate_percent: float

    @property
    def rate(self) -> float:
        return self.rate_percent / 100


@dataclass(frozen=True)
class ExpectedVisitorEstimate:
    """
    単一の入店率シナリオに対する期待来店数。

    Attributes:
        label: 画面に表示するシナリオ名。
        entry_rate_percent: 入店率のパーセント値。
        visitors_per_hour: 1時間あたりの期待来店数。
    """

    label: str
    entry_rate_percent: float
    visitors_per_hour: float


@dataclass(frozen=True)
class LocationRiskAssessment:
    """
    単一地点の通行量依存リスクを表す評価結果。

    Attributes:
        pedestrian_count_per_hour: 1時間あたりの店前通行量。
        estimates: 入店率シナリオ別の期待来店数。
        risk_label: 通行量依存で見たリスク区分。
        recommendation: 推奨する集客方針。
    """

    pedestrian_count_per_hour: int
    estimates: list[ExpectedVisitorEstimate]
    risk_label: str
    recommendation: str
