from dataclasses import dataclass


@dataclass
class Axis:
    axis: str
    value: float

    def to_dict(self) -> dict:
        return {"axis": self.axis, "value": self.value}


@dataclass
class Layer:
    name: str
    axes: list[Axis]

    def to_dict(self) -> dict:
        return {"name": self.name, "axes": [axis.to_dict() for axis in self.axes]}


@dataclass
class RadarChart:
    layers: list[Layer]

    def to_dict(self) -> dict:
        return {"layers": [layer.to_dict() for layer in self.layers]}
