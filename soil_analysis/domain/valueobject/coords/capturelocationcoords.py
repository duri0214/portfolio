from soil_analysis.domain.valueobject.coords.basecoords import BaseCoords
from soil_analysis.domain.valueobject.coords.googlemapcoords import GoogleMapCoords


class CaptureLocationCoords(BaseCoords):
    def __init__(self, longitude: float, latitude: float):
        """
        撮影座標 は 経度緯度(lng, lat) で作成する
        """
        self.longitude = longitude
        self.latitude = latitude

    def get_coords(self, to_str: bool = False) -> tuple[float, float] or str:
        """
        :return: longitude, latitude
        """
        coordinates_tuple = self.longitude, self.latitude
        coordinates_str = f"{coordinates_tuple[0]}, {coordinates_tuple[1]}"
        return coordinates_tuple if to_str is False else coordinates_str

    def to_googlemapcoords(self) -> GoogleMapCoords:
        return GoogleMapCoords(self.latitude, self.longitude)
