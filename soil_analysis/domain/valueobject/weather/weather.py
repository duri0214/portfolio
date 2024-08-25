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
