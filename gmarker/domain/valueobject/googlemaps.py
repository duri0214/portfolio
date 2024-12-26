from dataclasses import dataclass

from lib.geo.valueobject.coords import GoogleMapCoords


@dataclass
class PlacePhoto:
    height: int
    width: int
    html_attributions: list[str]
    photo_reference: str


@dataclass
class PlaceDetail:
    formatted_address: str | None
    formatted_phone_number: str | None
    opening_hours: dict | None
    price_level: int | None
    rating: float | None
    reviews: list | None
    types: list[str] | None
    website: str | None


@dataclass
class PlaceVO:
    """
    このデータクラスは、Google Places APIから取得した場所の詳細情報を表します。

    プロパティ:
        search_word: 場所の検索ワード
        place_id: 場所のGoogle Places IDを表す文字列
        name: 場所の名前を表す文字列です。
        location: 場所の座標
        photos: 場所の写真のリスト
        reviews: 場所のレビューを表す文字列のリスト
        is_status_ok: APIからのレスポンスにエラーがなかった場合にTrue
    """

    search_word: str
    place_id: str
    name: str
    location: GoogleMapCoords
    photos: list[PlacePhoto]
    detail: PlaceDetail | None
