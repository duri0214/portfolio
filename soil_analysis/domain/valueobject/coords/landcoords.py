from soil_analysis.domain.valueobject.coords.basecoords import BaseCoords
from soil_analysis.domain.valueobject.coords.googlemapcoords import GoogleMapCoords


class LandCoords(BaseCoords):
    def __init__(self, coords_str: str):
        """
        xarvioは圃場情報を 経度緯度(lng, lat) のタプルを4以上で構成し、その4以上の座標をspaceで区切ってエクスポートする
        See Also: https://developers.google.com/kml/documentation/kmlreference?hl=ja#coordinates
        """
        coords = coords_str.split()
        coords = list(set(coords))  # 始点と終点の座標が一致するため、重複を排除する
        self.latitude_sum = 0.0
        self.longitude_sum = 0.0
        self.num_points = len(coords)
        for coord in coords:
            lng, lat = coord.split(',')
            self.longitude_sum += float(lng)
            self.latitude_sum += float(lat)
        self.longitude = round(self.longitude_sum / self.num_points, 7)
        self.latitude = round(self.latitude_sum / self.num_points, 7)

    def get_coords(self, to_str: bool = False) -> tuple[float, float] or str:
        coordinates_tuple = self.longitude, self.latitude
        coordinates_str = f"{coordinates_tuple[0]}, {coordinates_tuple[1]}"
        return coordinates_tuple if to_str is False else coordinates_str

    def to_googlemapcoords(self) -> GoogleMapCoords:
        return GoogleMapCoords(self.latitude, self.longitude)
