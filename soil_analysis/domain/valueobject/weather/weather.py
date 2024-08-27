from dataclasses import dataclass


@dataclass
class WeatherCodeRaw:
    code: str
    image_day: str
    image_night: str
    summary_code: str
    name: str
    name_en: str


@dataclass
class JmaConst:
    code: str
    name: str
    children: list[str]
    parent: str


@dataclass
class RegionWeather:
    """
    weather information for a specific region.

    Attributes:
      region_code (str): The code of the region.
      region_name (str): The name of the region.
      weather_code (str): The code representing the weather in the region.
    """

    region_code: str
    region_name: str
    weather_code: str


@dataclass
class Amedas:
    """
    Amedas temperature data.

    Attributes:
        code (str): The code associated with the Amedas station.
        min_temps (float): The minimum temperature data.
        max_temps (float): The maximum temperature data.
    """

    code: str
    min_temps: float
    max_temps: float
