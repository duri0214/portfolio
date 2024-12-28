import requests

from gmarker.domain.valueobject.googlemaps import PlacePhoto, PlaceVO, PlaceDetail
from lib.geo.valueobject.coords import GoogleMapCoords


class GoogleMapsService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://places.googleapis.com/v1/places"

    def nearby_search(
        self,
        center: GoogleMapCoords,
        search_types: list[str],
        radius: int,
        fields: list[str],
    ) -> list[PlaceVO]:
        """
        Google Maps Places APIのNearby Search (New)を使用して施設を検索します。

        Args:
            center: 検索中心の座標。
            search_types: 検索する場所のタイプ。
            radius: 検索半径（メートル）。
            fields: 取得するフィールドのリスト。

        Returns:
            検索結果の施設リスト。

        Raises:
            requests.HTTPError: HTTPエラーが発生した場合。
            ValueError: fieldsが空の場合。
        """

        if not fields:
            raise ValueError("fieldsパラメータは必須です")

        url = f"{self.base_url}:searchNearby"

        request_body = {
            "locationRestriction": {
                "circle": {
                    "center": {
                        "latitude": center.latitude,
                        "longitude": center.longitude,
                    },
                    "radius": radius,
                }
            },
            "includedTypes": search_types,
            "languageCode": "ja",
        }

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": ",".join(fields),
        }

        try:
            response = requests.post(url, headers=headers, json=request_body)
            response.raise_for_status()
            data = response.json()
            places_data = data.get("places", [])

            places: list[PlaceVO] = []
            for place_data in places_data:
                latlng = place_data.get("location")
                if latlng:
                    latlng = GoogleMapCoords(
                        latitude=latlng.get("latitude"),
                        longitude=latlng.get("longitude"),
                    )

                photos = []
                for photo in place_data.get("photos", []):
                    author_attributions = photo.get("authorAttributions", [])[0]
                    photos.append(
                        PlacePhoto(
                            width=photo.get("widthPx"),
                            height=photo.get("heightPx"),
                            author_name=author_attributions.get("displayName"),
                            author_url=author_attributions.get("uri"),
                            author_photo_uri=author_attributions.get("photoUri"),
                        )
                    )

                places.append(
                    PlaceVO(
                        place_id=place_data.get("id"),
                        location=latlng,
                        name=place_data.get("displayName", {}).get("text"),
                        address=place_data.get("formattedAddress"),
                        photos=photos,
                        detail=None,
                    )
                )
            return places

        except requests.HTTPError as e:
            print(f"An HTTP error occurred: {e}")
            return []
        except (KeyError, TypeError) as e:
            print(f"A data parsing error occurred: {e}")
            return []
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return []

    def get_place_details(self, place_vo: PlaceVO, fields: list[str]) -> PlaceVO | None:
        """
        Place Details APIを使用して場所の詳細情報を取得し、PlaceVOを更新します。

        Args:
            place_vo: 更新するPlaceVOオブジェクト。
            fields: 取得するフィールドのリスト。

        Returns:
            更新されたPlaceVOオブジェクト。エラー時はNone。

        Raises:
            ValueError: fieldsが空の場合。
        """
        if not fields:
            raise ValueError("fieldsパラメータは必須です")

        place_id = place_vo.place_id
        if not place_id:
            print("place_idがありません")
            return None

        url = f"{self.base_url}/{place_id}"

        params = {"fields": ",".join(fields), "key": self.api_key}
        headers = {
            "X-Goog-Api-Key": self.api_key,
        }

        try:
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            result = response.json().get("result")
            if result:
                place_vo.detail = PlaceDetail(
                    formatted_address=result.get("formatted_address"),
                    formatted_phone_number=result.get("formatted_phone_number"),
                    opening_hours=result.get("opening_hours"),
                    price_level=result.get("price_level"),
                    rating=result.get("rating"),
                    reviews=result.get("reviews"),
                    types=result.get("types"),
                    website=result.get("website"),
                )

                location_data = result.get("geometry", {}).get("location")
                if location_data:
                    place_vo.location = GoogleMapCoords(
                        latitude=location_data.get("lat"),
                        longitude=location_data.get("lng"),
                    )
            return place_vo
        except requests.HTTPError as e:
            print(f"An HTTP error occurred: {e}")
        except KeyError as e:
            print(f"KeyError occurred: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")
        return None
