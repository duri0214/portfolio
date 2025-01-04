from dataclasses import dataclass

from lib.geo.valueobject.coords import GoogleMapCoords


@dataclass
class PlacePhoto:
    width: int | None
    height: int | None
    author_name: str | None
    author_url: str | None
    author_photo_uri: str | None


@dataclass
class PlaceVO:
    """
    このデータクラスは、Google Places APIから取得する場所の詳細情報を表します。

    プロパティ:
        place_id: 場所のGoogle Places IDを表現する文字列。
        location: 場所の座標を表現するGoogleMapCoordsのインスタンス。
        name: 場所の名前を表現する文字列。
        photos: 場所の写真を格納するPlacePhotoのインスタンスのリスト。
        detail: 場所の詳細情報を表現するPlaceDetailのインスタンス（将来的にレビュー情報が含まれる可能性あり）。
    """

    place_id: str
    location: GoogleMapCoords
    name: str
    photos: list[PlacePhoto] | None
    rating: float
    reviews: list
