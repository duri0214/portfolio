import requests

from gmarker.domain.valueobject.googlemaps import PlacePhoto, PlaceVO
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
                        photos=photos,
                        rating=place_data.get("rating"),
                        reviews=place_data.get("reviews"),
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

    def get_place_details(self, place_id: str, fields: list[str]) -> PlaceVO | None:
        """
        Place Details APIを使用して場所の詳細情報を取得し、PlaceVOオブジェクトを返します。

        Args:
            place_id (str): 取得する場所のプレイスID。必須。
            fields (list[str]): 取得するフィールドのリスト。必須。
                指定可能なフィールドについては、Google Maps Platformのドキュメントを参照してください。
                https://developers.google.com/maps/documentation/places/web-service/place-details?hl=ja

        Returns:
            PlaceVO | None: 取得された場所の詳細情報を持つPlaceVOオブジェクト。
                APIリクエストの失敗などの場合はNoneを返します。

        Raises:
            ValueError: fieldsリストが空の場合に発生します。

        Exceptions:
            requests.HTTPError: HTTPエラーが発生した場合にログ出力します。
            KeyError: JSONレスポンスに予期しないキーが含まれていた場合にログ出力します。
            Exception: その他の予期しないエラーが発生した場合にログ出力します。
        """
        if not fields:
            raise ValueError("fieldsパラメータは必須です")

        url = f"{self.base_url}/{place_id}"

        params = {"fields": ",".join(fields), "key": self.api_key}
        headers = {
            "X-Goog-Api-Key": self.api_key,
        }

        try:
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            result = response.json().get("result")

            if not result:
                print(f"No result found for place_id: {place_id}")
                return None

            location_data = result.get("geometry", {}).get("location")
            location = (
                GoogleMapCoords(
                    latitude=location_data.get("lat"),
                    longitude=location_data.get("lng"),
                )
                if location_data
                else None
            )

            place_vo = PlaceVO(
                place_id=place_id,
                location=location,
                name=result.get("name"),
                photos=result.get("photos", []),
                rating=result.get("rating"),
                reviews=result.get("reviews", []),
            )
            return place_vo
        except requests.HTTPError as e:
            print(f"An HTTP error occurred: {e}")
        except KeyError as e:
            print(f"KeyError occurred: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")
        return None
