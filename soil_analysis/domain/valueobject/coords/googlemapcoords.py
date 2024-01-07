from soil_analysis.domain.valueobject.coords.basecoords import BaseCoords


class GoogleMapCoords(BaseCoords):
    def __init__(self, latitude: float, longitude: float):
        """
        googlemap は 緯度経度(lat, lng) で作成する
        """
        self.latitude = latitude
        self.longitude = longitude

    def get_coords(self, to_str: bool = False) -> tuple[float, float] or str:
        """
        :return: latitude, longitude
        """
        coordinates_tuple = self.latitude, self.longitude
        coordinates_str = f"{coordinates_tuple[0]}, {coordinates_tuple[1]}"
        return coordinates_tuple if to_str is False else coordinates_str
