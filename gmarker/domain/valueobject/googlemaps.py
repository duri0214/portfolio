from dataclasses import dataclass

from lib.geo.valueobject.coords import GoogleMapCoords


@dataclass
class PlaceVO:
    """
    このデータクラスは、Google Places APIから取得した場所の詳細情報を表します。

    プロパティ:
        place_id: 場所のGoogle Places IDを表す文字列。
        location: 場所の座標を表すGoogleMapCoordsのインスタンス。
        name: 場所の名前を表す文字列。
        rating: 場所の評価を表す浮動小数点数。
        reviews: 将来的に場所のレビュー情報を含む可能性があるリスト。
    """

    place_id: str
    location: GoogleMapCoords
    name: str
    rating: float
    reviews: list
