from dataclasses import dataclass, field

from lib.geo.valueobject.coord import GoogleMapsCoord


@dataclass(frozen=True)
class GoogleMapsReviewData:
    """
    Google Maps Places API から取得したレビュー1件。

    Attributes:
        text: レビュー本文。
        author: レビュー投稿者名。
        publish_time: レビュー公開日時の文字列。
        google_maps_uri: レビューまたは施設の Google Maps URL。
    """

    text: str | None
    author: str | None
    publish_time: str | None
    google_maps_uri: str | None


@dataclass(frozen=True)
class GoogleMapsPlaceData:
    """
    出店計画レビュー取得で使う Google Maps 施設データ。

    Attributes:
        place_id: Google Maps の Place ID。
        location: 施設の座標。
        name: 施設名。
        rating: 施設の Google Maps rating。
        reviews: 施設に紐づくレビュー一覧。
    """

    place_id: str
    location: GoogleMapsCoord | None
    name: str | None
    rating: float | None
    reviews: list[GoogleMapsReviewData] = field(default_factory=list)
