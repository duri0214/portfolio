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


@dataclass
class Coord:
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

    min_coord: Coord  # 左下のピクセル座標
    max_coord: Coord  # 右上のピクセル座標

    @property
    def width(self) -> int:
        """矩形の幅を計算"""
        return self.max_coord.x - self.min_coord.x

    @property
    def height(self) -> int:
        """矩形の高さを計算"""
        return self.max_coord.y - self.min_coord.y

    def to_tuple(self) -> tuple[tuple[int, int], tuple[int, int]]:
        """矩形座標をタプル形式で返す"""
        return self.min_coord.to_tuple(), self.max_coord.to_tuple()
