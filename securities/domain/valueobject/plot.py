import datetime
from dataclasses import dataclass


@dataclass
class RequestData:
    start_date: datetime.date
    end_date: datetime.date

    def __post_init__(self):
        if self.start_date > datetime.date.today():
            raise ValueError("start_date is in the future")
        if self.end_date > datetime.date.today():
            raise ValueError("end_date is in the future")
        if self.start_date > self.end_date:
            raise ValueError("start_date is later than end_date")


@dataclass
class PlotParams:
    """
    Attributes:
        x (str): プロットのx軸のラベル
        title (str | None): グラフタイトルとファイル名に使用される

    Notes: 使用するグラフが横軸なので single版(i.e. this) は x という名前になるので縦にするときは注意
    """

    x: str
    title: str | None


@dataclass
class PlotParamsForKDE(PlotParams):
    """
    Attributes:
        y (str): プロットのy軸のラベル
        color (str): KDEプロットに使用する色
    """

    y: str
    color: str
