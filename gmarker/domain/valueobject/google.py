from dataclasses import dataclass

from gmarker.models import Place
from lib.geo.valueobject.coord import GoogleMapsCoord


@dataclass
class RequestBody:
    """
    Google Maps Places APIでNearby Searchのリクエストボディを表現するVO。

    Attributes:
        center: 検索の中心座標をGoogleMapsCoordで受け取る。
        radius: 検索範囲の半径（メートル）。
        search_types: 検索タイプのリスト。
        lang: 使用する言語（デフォルトは日本語 "ja"）。
    """

    center: GoogleMapsCoord
    radius: int
    search_types: list[str]
    lang: str = "ja"

    def to_dict(self) -> dict:
        """
        VOをAPIリクエストのJSON形式に変換。

        Returns:
            dict: リクエストボディを表す辞書データ。
        """
        return {
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": self.center.latitude,
                        "longitude": self.center.longitude,
                    },
                    "radius": self.radius,
                }
            },
            "includedTypes": self.search_types,
            "languageCode": self.lang,
        }


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
        location: 場所の座標を表すGoogleMapsCoordのインスタンス。
        name: 場所の名前を表す文字列。
        rating: 場所の評価を表す浮動小数点数。
        reviews: 将来的に場所のレビュー情報を含む可能性があるリスト。
    """

    place: Place
    location: GoogleMapsCoord
    name: str
    rating: float
    reviews: list[ReviewVO]
