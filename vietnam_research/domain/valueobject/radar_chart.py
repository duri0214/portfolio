from dataclasses import dataclass


@dataclass
class Axis:
    axis: str
    value: float

    def to_dict(self) -> dict:
        return {"axis": self.axis, "value": self.value}


@dataclass
class RadarChartLayer:
    name: str
    axes: list[Axis]

    def to_dict(self) -> dict:
        return {"name": self.name, "axes": [axis.to_dict() for axis in self.axes]}
