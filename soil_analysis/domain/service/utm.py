from math import isfinite

from pyproj import Transformer
from pyproj.enums import TransformDirection


def _transformer(zone: int, northern: bool) -> Transformer:
    if type(zone) is not int or not 1 <= zone <= 60:
        raise ValueError("UTM zone must be an integer between 1 and 60")
    if type(northern) is not bool:
        raise ValueError("northern must be a boolean")
    epsg = (32600 if northern else 32700) + zone
    return Transformer.from_crs(4326, epsg, always_xy=True)


def to_utm(
    longitude: float, latitude: float, zone: int, northern: bool
) -> tuple[float, float]:
    """Project WGS84 longitude and latitude (degrees) to easting and northing (metres)."""
    transformer = _transformer(zone, northern)
    if not (
        isfinite(longitude)
        and isfinite(latitude)
        and -180 <= longitude <= 180
        and -80 <= latitude <= 84
    ):
        raise ValueError("coordinate is outside the UTM latitude or longitude range")
    if (northern and latitude < 0) or (not northern and latitude > 0):
        raise ValueError("latitude does not match the hemisphere")
    return transformer.transform(longitude, latitude, errcheck=True)


def from_utm(
    easting: float, northing: float, zone: int, northern: bool
) -> tuple[float, float]:
    """Convert WGS84 UTM easting and northing (metres) to longitude and latitude (degrees)."""
    transformer = _transformer(zone, northern)
    if not (
        isfinite(easting)
        and isfinite(northing)
        and 100000 <= easting <= 900000
        and 0 <= northing <= 10000000
    ):
        raise ValueError("coordinate is outside the supported UTM range")
    longitude, latitude = transformer.transform(
        easting, northing, direction=TransformDirection.INVERSE, errcheck=True
    )
    if (
        not (-80 <= latitude <= 84)
        or (northern and latitude < -1e-10)
        or (not northern and latitude > 1e-10)
    ):
        raise ValueError("coordinate is outside the UTM hemisphere or latitude range")
    return longitude, latitude
