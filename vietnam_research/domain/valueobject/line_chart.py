from dataclasses import dataclass


@dataclass(frozen=True)
class LineChartLayer:
    """
    折れ線グラフの1つのレイヤー（データ系列）を表す値オブジェクト。

    Attributes:
        label: データ系列のラベル名（例：銘柄名、指標名）。
        data: 数値データのリスト。
    """

    label: str
    data: list[float]

    def to_dict(self):
        return {"label": self.label, "data": self.data}
