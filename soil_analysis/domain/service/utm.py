from pyproj import Transformer
from pyproj.enums import TransformDirection

from soil_analysis.domain.valueobject.utm import (
    GeographicCoordinate,
    UtmCoordinate,
    UtmZone,
)


def _transformer(zone: UtmZone) -> Transformer:
    epsg = (32600 if zone.northern else 32700) + zone.number
    return Transformer.from_crs(4326, epsg, always_xy=True)


def to_utm(coordinate: GeographicCoordinate, zone: UtmZone) -> UtmCoordinate:
    """WGS84緯度経度を指定ゾーンのUTM座標に変換する。"""
    if (zone.northern and coordinate.latitude < 0) or (
        not zone.northern and coordinate.latitude > 0
    ):
        raise ValueError("latitude does not match the hemisphere")
    easting, northing = _transformer(zone).transform(
        coordinate.longitude, coordinate.latitude, errcheck=True
    )
    return UtmCoordinate(easting, northing, zone)


def from_utm(coordinate: UtmCoordinate) -> GeographicCoordinate:
    """WGS84 UTM座標を緯度経度に変換する。"""
    longitude, latitude = _transformer(coordinate.zone).transform(
        coordinate.easting,
        coordinate.northing,
        direction=TransformDirection.INVERSE,
        errcheck=True,
    )
    if (coordinate.zone.northern and latitude < -1e-10) or (
        not coordinate.zone.northern and latitude > 1e-10
    ):
        raise ValueError("coordinate is outside the UTM hemisphere")
    return GeographicCoordinate(longitude, latitude)
