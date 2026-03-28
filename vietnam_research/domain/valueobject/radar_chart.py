from dataclasses import dataclass


@dataclass(frozen=True)
class Axis:
    """
    レーダーチャートの単一の軸（評価項目と値）を表す値オブジェクト。

    Attributes:
        axis: 軸の名称（例：収益性、割安性）。
        value: その軸における評価数値。
    """

    axis: str
    value: float

    def to_dict(self) -> dict:
        return {"axis": self.axis, "value": self.value}


@dataclass(frozen=True)
class RadarChartLayer:
    """
    レーダーチャートの1つのレイヤー（データ系列）を表す値オブジェクト。

    Attributes:
        name: データ系列の名称（例：銘柄名、業界名）。
        axes: Axis オブジェクトのリスト。
    """

    name: str
    axes: list[Axis]

    def to_dict(self) -> dict:
        return {"name": self.name, "axes": [axis.to_dict() for axis in self.axes]}
