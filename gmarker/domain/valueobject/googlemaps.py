from dataclasses import dataclass

from gmarker.models import Place
from lib.geo.valueobject.coords import GoogleMapCoords


@dataclass
class ReviewVO:
    """
    このデータクラスは、Google Places APIから取得するレビューの詳細情報を表します。

    Attributes:
        text: レビューのテキストを表現する文字列。
        author: レビューの投稿者の名前を表す文字列。
        publish_time: レビューの公開時間を表す文字列。
        google_maps_uri: レビューに関連するGoogleマップのURIを表す文字列。

    """

    text: str
    author: str
    publish_time: str
    google_maps_uri: str


@dataclass
class PlaceVO:
    """
    このデータクラスは、Google Places APIから取得した場所の詳細情報を表します。

    Attributes:
        place: このレビューが関連付けられるPlaceモデルのインスタンス。
        location: 場所の座標を表すGoogleMapCoordsのインスタンス。
        name: 場所の名前を表す文字列。
        rating: 場所の評価を表す浮動小数点数。
        reviews: 将来的に場所のレビュー情報を含む可能性があるリスト。
    """

    place: Place
    location: GoogleMapCoords
    name: str
    rating: float
    reviews: list[ReviewVO]
