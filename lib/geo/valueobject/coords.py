from abc import ABC, abstractmethod
from dataclasses import dataclass

from affine import Affine
from rasterio.crs import CRS


@dataclass
class MetaData:
    """
    GeoTIFFファイルのメタデータを表現するクラス。

    Attributes:
        driver (str): データ形式 (例: 'GTiff')
        dtype (str): データ型 (例: 'uint16')
        nodata (None | float | int): データが存在しない領域を表す値。
        width (int): 画像の横幅（ピクセル単位）。
        height (int): 画像の縦幅（ピクセル単位）。
        count (int): 画像内のバンド（レイヤー）の数。
        crs (CRS | None): 座標参照系を表すオブジェクト。
            例: WGS 84の場合、`CRS.from_epsg(4326)`。
            Noneの場合、座標参照系が定義されていない。
        transform (Affine): アフィン変換行列。
            画像のピクセル座標と地理座標を関連付けるための行列。
    """

    driver: str
    dtype: str
    nodata: None | float | int
    width: int
    height: int
    count: int
    crs: CRS | None
    transform: Affine


class BaseCoords(ABC):
    def __init__(self, latitude: float, longitude: float):
        self.latitude = latitude
        self.longitude = longitude

    @abstractmethod
    def to_tuple(self) -> tuple[float, float]:
        """
        座標をタプル形式で取得します。具体的な順序はサブクラスによります。

        Returns:
            tuple[float, float]: 座標を表すタプル
        """
        pass

    @abstractmethod
    def to_str(self) -> str:
        """
        座標を文字列形式で取得します。具体的な順序はサブクラスによります。

        Returns:
            str: 座標を表す文字列
        """
        pass


class GoogleMapCoords(BaseCoords):
    """
    Google Map 用の座標変換クラス。BaseCoordsを継承します。

    メソッド:
    to_tuple: 座標をタプル形式で取得します。戻り値は (緯度,経度) 形式です。
    to_str : 座標を文字列形式で取得します。戻り値は "緯度, 経度" 形式です。
    """

    def to_tuple(self) -> tuple[float, float]:
        return self.latitude, self.longitude

    def to_str(self) -> str:
        return f"{self.latitude}, {self.longitude}"


@dataclass
class Point:
    """
    ピクセル座標を表すクラス。
    """

    x: int
    y: int

    def to_tuple(self) -> tuple[int, int]:
        """タプル形式に変換する"""
        return self.x, self.y


@dataclass
class RectangleCoords:
    """
    矩形の座標範囲を表す Value Object。
    左下（西南）と右上（北東）のピクセル座標を保持する。
    """

    min_point: Point  # 左下のピクセル座標
    max_point: Point  # 右上のピクセル座標

    @property
    def width(self) -> int:
        """矩形の幅を計算"""
        return self.max_point.x - self.min_point.x

    @property
    def height(self) -> int:
        """矩形の高さを計算"""
        return self.max_point.y - self.min_point.y

    def to_tuple(self) -> tuple[tuple[int, int], tuple[int, int]]:
        """矩形座標をタプル形式で返す"""
        return self.min_point.to_tuple(), self.max_point.to_tuple()


class CaptureLocationCoords(BaseCoords):
    """
    Capture Location 用の座標変換クラス。BaseCoordsを継承します。
    xarvio用に作ったので、順序が Google Map とは異なり、(経度,緯度)です。
    ※写真側の緯度経度取り扱い形式にしないといけないのかもしれない

    メソッド:
    to_tuple: 座標をタプル形式で取得します。戻り値は (経度,緯度) 形式です。
    to_str : 座標を文字列形式で取得します。戻り値は "経度, 緯度" 形式です。
    to_googlemap: CaptureLocation 用の座標を GoogleMapCoords に変換します。
    """

    def to_tuple(self) -> tuple[float, float]:
        return self.longitude, self.latitude

    def to_str(self) -> str:
        return f"{self.longitude}, {self.latitude}"

    def to_googlemap(self) -> GoogleMapCoords:
        return GoogleMapCoords(self.latitude, self.longitude)


class LandCoords(BaseCoords):
    def __init__(self, coords_str: str):
        """
        Land 用の座標変換クラス。BaseCoordsを継承します。
        xarvio用に作ったので、順序が Google Map とは異なり、(経度,緯度)です。

        メソッド:
        to_tuple: 座標をタプル形式で取得します。戻り値は (経度,緯度) 形式です。
        to_str : 座標を文字列形式で取得します。戻り値は "経度, 緯度" 形式です。
        to_googlemap: Land 用の座標を GoogleMapCoords に変換します。

        Notes:
        xarvioは圃場情報を 経度緯度(lng, lat) のタプルで4以上（通常5）で構成し、その座標をスペースで区切ってエクスポートします。たとえば：
        <coordinates>137.6489657,34.7443565 137.6491266,34.744123 137.648613,34.7438929
        137.6484413,34.7441175 137.6489657,34.7443565</coordinates>
        上記の座標は1つの圃場を表し、最初と最後の座標は同じ位置を示しています（縮小ループ）。

        See Also: https://developers.google.com/kml/documentation/kmlreference?hl=ja#coordinates
        """
        super().__init__(0.0, 0.0)  # initial values set to zero

        coords = coords_str.split()
        coords = list(set(coords))  # 始点と終点の座標が一致するため、重複を排除する
        latitude_sum = 0.0
        longitude_sum = 0.0
        num_points = len(coords)

        for coord in coords:
            lng, lat = coord.split(",")
            longitude_sum += float(lng)
            latitude_sum += float(lat)

        self.longitude = round(longitude_sum / num_points, 7)
        self.latitude = round(latitude_sum / num_points, 7)

    def to_tuple(self) -> tuple[float, float]:
        return self.longitude, self.latitude

    def to_str(self) -> str:
        return f"{self.longitude}, {self.latitude}"

    def to_googlemap(self) -> GoogleMapCoords:
        return GoogleMapCoords(self.latitude, self.longitude)
