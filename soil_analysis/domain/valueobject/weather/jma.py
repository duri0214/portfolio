from dataclasses import dataclass


# マスタデータ
@dataclass
class JmaConstWeatherCode:
    """
    気象庁の定数マスタ（天気コード）

    Attributes:
        code (str): The code of the weather.
        image_day (str): The image path for day weather.
        image_night (str): The image path for night weather.
        summary_code (str): The summary code for the weather.
        name (str): The name of the weather.
        name_en (str): The English name of the weather.
    """

    code: str
    image_day: str
    image_night: str
    summary_code: str
    name: str
    name_en: str


@dataclass
class JmaConstGeographicArea:
    """
    気象庁の定数マスタ（area, prefecture, region, city_group, city）

    Attributes:
        code (str): The code of the constant.
        name (str): The name of the constant.
        children (list[str]): The list of children constants' codes.
        parent (str): The code of the parent constant.
    """

    code: str
    name: str
    children: list[str]
    parent: str


# 予報データ
class MeanCalculable:
    """
    平均を出すための生値とその平均値

    Args:
        float_list (list[float]): 生値
    """

    def __init__(self, float_list: list[float]) -> None:
        self.raw: list[float] = float_list
        self.mean: float = (
            round(sum(float_list) / len(float_list), 1) if float_list else 0
        )


@dataclass(frozen=True)
class Region:
    """
    A class representing a region.

    Attributes:
        code (str): "280010"
        name (str): "南部"
    """

    code: str
    name: str


@dataclass(frozen=True)
class SummaryText:
    """
    気象情報: サマリー情報

    Attributes:
        weather (str): "雨　所により　雷を伴い　非常に　激しく　降る"
        wind (str): "東の風　やや強く　海上　では　東の風　強く"
        wave (str): "１．５メートル　ただし　淡路島南部　では　３メートル　うねり　を伴う"
    """

    weather: str
    wind: str
    wave: str


@dataclass(frozen=True)
class RainData:
    """
    気象情報: 降水確率

    Attributes:
        values (MeanCalculable): 生値とその平均値（時間帯平均）
        unit (str): "%"
    """

    values: MeanCalculable
    unit: str = "%"


@dataclass(frozen=True)
class TemperatureData:
    """
    気象情報: 気温

    Attributes:
        min_values (MeanCalculable): 生値とその平均値（region平均）
        max_values (MeanCalculable): 生値とその平均値（region平均）
        unit (str): "℃"
    """

    min_values: MeanCalculable
    max_values: MeanCalculable
    unit: str = "℃"


class WindData:
    """
    気象情報: 最大風速

    Attributes:
        values (MeanCalculable): 生値とその平均値（時間帯平均）
        unit (str): "以下" or "メートル毎秒"

    Notes: 風速値が9のばあい、その object に condition というキーが現れて "以下" という値が入るが
     表現を間引いて、平均値が9以下だったら "以下" にすることにした
    """

    def __init__(self, values: MeanCalculable):
        self.values = values
        self.unit = "以下" if self.values.mean <= 9 else "メートル毎秒"

    def __str__(self):
        return f"最大風速（時間帯平均）は {self.values.mean} {self.unit}"
