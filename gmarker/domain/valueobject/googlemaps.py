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
    このデータクラスは、Google Places APIから取得する場所の詳細情報を表します。

    プロパティ:
        place_id: 場所のGoogle Places IDを表現する文字列。
        location: 場所の座標を表現するGoogleMapCoordsのインスタンス。
        name: 場所の名前を表現する文字列。
        address: 場所の住所を表現する文字列。
        photos: 場所の写真を格納するPlacePhotoのインスタンスのリスト。
        detail: 場所の詳細情報を表現するPlaceDetailのインスタンス（将来的にレビュー情報が含まれる可能性あり）。
    """

    place_id: str | None
    location: GoogleMapCoords | None
    name: str | None
    address: str | None
    photos: list[PlacePhoto] | None
    detail: PlaceDetail | None  # TODO: reviewが入るといいな
