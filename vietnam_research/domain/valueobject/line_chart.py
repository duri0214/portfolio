from dataclasses import dataclass


@dataclass
class LineChartLayer:
    label: str
    data: list[float]

    def to_dict(self):
        return {"label": self.label, "data": self.data}
