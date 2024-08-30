from dataclasses import dataclass
from datetime import datetime


# マスタデータ
@dataclass
class WeatherCodeRaw:
    """
    気象庁の定数マスタ（天気コード）
    # TODO: クラス名を考えて（JmaConstWeatherRaw?）

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
class JmaConst:
    """
    気象庁の定数マスタ（area, prefecture, region, city_group, city）
    # TODO: クラス名を考えて（JmaConstRaw? segment?）

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
        self.values: list[float] = float_list
        self.mean: float = sum(float_list) / len(float_list) if float_list else 0


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


@dataclass(frozen=True)
class WindData:
    """
    気象情報: 最大風速

    Attributes:
        values (MeanCalculable): 生値とその平均値（時間帯平均）
        unit (str): "以下" or "メートル毎秒"
    """

    values: MeanCalculable
    unit: str


@dataclass(frozen=True)
class WeatherData:
    """
    気象情報: 1日分の天気情報

    Attributes:

    Attributes:
        time_defined (datetime): "2024-08-29T17:00:00+09:00"
        code (str): "300"
        summary_text (SummaryText): "雨　所により　雷を伴い　非常に　激しく　降る"
        rain_data (RainData): "60%"
        temperature_data (TemperatureData): "25℃"
        wind_data (WindData): 9以下
    """

    time_defined: datetime
    code: str
    summary_text: SummaryText
    rain_data: RainData
    temperature_data: TemperatureData
    wind_data: WindData


class WeatherForecast:
    """
    気象情報: 何日ぶんかの天気情報を持った天気予報

    Args:
        region (Region): The region for which the weather forecast is generated.
        weather_data (list[WeatherData]): A list of WeatherData objects representing the forecast data.

    Attributes:
        region (Region): The region for which the weather forecast is generated.
        weather_data (list[WeatherData]): A list of WeatherData objects representing the forecast data.
    """

    def __init__(
        self,
        region: Region,
        weather_data: list[WeatherData],
    ):
        self.region = region
        self.weather_data = weather_data



