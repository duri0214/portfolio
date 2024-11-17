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
    def get_coords(self, to_str: bool = False) -> tuple[float, float] | str:
        """
        座標（緯度と経度）を取得します。結果の形式は、引数 `to_str` により制御されます。

        引数 `to_str` が False の場合、このメソッドは緯度と経度を包含するタプルを返します。
        True の場合、緯度と経度を文字列形式で返します。緯度と経度はカンマで区切られます。

        パラメータ:
        to_str (bool, optional): 結果を文字列として返すかどうか。デフォルトは False。

        戻り値:
        tuple[float, float] | str: 緯度と経度を含むタプルまたは緯度と経度をカンマで区切った文字列。

        Raises:
        NotImplementedError: このメソッドは、すべての派生クラスで実装する必要があります。
        """
        pass


class GoogleMapCoords(BaseCoords):
    def get_coords(self, to_str: bool = False) -> tuple[float, float] | str:
        """
        TODO: to_strとto_tupleにMethodに割ったほうがいい
        :return: latitude, longitude
        """
        coordinates_tuple = self.latitude, self.longitude
        coordinates_str = f"{coordinates_tuple[0]}, {coordinates_tuple[1]}"
        return coordinates_tuple if to_str is False else coordinates_str


class CaptureLocationCoords(BaseCoords):
    def get_coords(self, to_str: bool = False) -> tuple[float, float] | str:
        """
        :return: longitude, latitude
        """
        coordinates_tuple = self.longitude, self.latitude
        coordinates_str = f"{coordinates_tuple[0]}, {coordinates_tuple[1]}"
        return coordinates_tuple if to_str is False else coordinates_str

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

    def get_coords(self, to_str: bool = False) -> tuple[float, float] or str:
        coordinates_tuple = self.longitude, self.latitude
        coordinates_str = f"{coordinates_tuple[0]}, {coordinates_tuple[1]}"
        return coordinates_tuple if to_str is False else coordinates_str

    def to_googlemap(self) -> GoogleMapCoords:
        return GoogleMapCoords(self.latitude, self.longitude)
