from abc import ABC, abstractmethod


class BaseCoords(ABC):
    """
    座標を表すベースクラス。緯度と経度を持つ。

    メソッド:
    get_coords : 座標を取得します。戻り値の形式を指定することもできます。

    抽象メソッド:
    get_coords
    """

    def __init__(self, latitude: float, longitude: float):
        """
        BaseCoords クラスのインスタンスを生成します。

        パラメータ:
        latitude (float): 緯度
        longitude (float): 経度
        """
        self.latitude = latitude
        self.longitude = longitude

    @abstractmethod
    def to_tuple(self) -> tuple[float, float]:
        pass

    @abstractmethod
    def to_str(self) -> str:
        pass


class GoogleMapCoords(BaseCoords):
    def to_tuple(self) -> tuple[float, float]:
        return self.latitude, self.longitude

    def to_str(self) -> str:
        return f"{self.latitude}, {self.longitude}"


class CaptureLocationCoords(BaseCoords):
    def to_tuple(self) -> tuple[float, float]:
        return self.longitude, self.latitude

    def to_str(self) -> str:
        return f"{self.longitude}, {self.latitude}"

    def to_googlemap(self) -> GoogleMapCoords:
        return GoogleMapCoords(self.latitude, self.longitude)


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
            lng, lat = coord.split(",")
            self.longitude_sum += float(lng)
            self.latitude_sum += float(lat)
        self.longitude = round(self.longitude_sum / self.num_points, 7)
        self.latitude = round(self.latitude_sum / self.num_points, 7)

    def to_tuple(self) -> tuple[float, float]:
        return self.longitude, self.latitude

    def to_str(self) -> str:
        return f"{self.longitude}, {self.latitude}"

    def to_googlemap(self) -> GoogleMapCoords:
        return GoogleMapCoords(self.latitude, self.longitude)
