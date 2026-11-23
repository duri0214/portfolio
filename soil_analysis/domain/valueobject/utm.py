from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class GeographicCoordinate:
    """UTMに変換できるWGS84緯度経度。

    Attributes:
        longitude (float): 経度（度）。
        latitude (float): 緯度（度）。
    """

    longitude: float
    latitude: float

    def __post_init__(self):
        if not (
            isfinite(self.longitude)
            and isfinite(self.latitude)
            and -180 <= self.longitude <= 180
            and -80 <= self.latitude <= 84
        ):
            raise ValueError(
                "coordinate is outside the UTM latitude or longitude range"
            )


@dataclass(frozen=True)
class UtmZone:
    """WGS84 UTM投影のゾーンと半球。

    Attributes:
        number (int): ゾーン番号（1〜60）。
        northern (bool): 北半球の場合はTrue、南半球の場合はFalse。
    """

    number: int
    northern: bool

    def __post_init__(self):
        if type(self.number) is not int or not 1 <= self.number <= 60:
            raise ValueError("UTM zone must be an integer between 1 and 60")
        if type(self.northern) is not bool:
            raise ValueError("northern must be a boolean")


@dataclass(frozen=True)
class UtmCoordinate:
    """WGS84 UTM座標と、その解釈に必要なゾーン・半球。

    Attributes:
        easting (float): 東距（メートル）。
        northing (float): 北距（メートル）。
        zone (UtmZone): ゾーンと半球。
    """

    easting: float
    northing: float
    zone: UtmZone

    def __post_init__(self):
        if not isinstance(self.zone, UtmZone):
            raise ValueError("zone must be a UtmZone")
        if not (
            isfinite(self.easting)
            and isfinite(self.northing)
            and 100000 <= self.easting <= 900000
            and 0 <= self.northing <= 10000000
        ):
            raise ValueError("coordinate is outside the supported UTM range")
