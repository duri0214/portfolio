import requests

from gmarker.domain.valueobject.googlemaps import PlaceVO
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

                places.append(
                    PlaceVO(
                        place_id=place_data.get("id"),
                        location=latlng,
                        name=place_data.get("displayName", {}).get("text"),
                        rating=place_data.get("rating"),
                        reviews=[
                            x.get("text").get("text") for x in place_data.get("reviews")
                        ],
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
