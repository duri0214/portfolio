import requests

from lib.geo.valueobject.coord import GoogleMapsCoord
from shopping.domain.valueobject.google_maps_reviews import (
    GoogleMapsPlaceData,
    GoogleMapsReviewData,
)


class GoogleMapsReviewClient:
    """出店計画のレビュー取得に必要な Places API だけを呼び出すHTTPクライアント。"""

    TIMEOUT_SECONDS = 10

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://places.googleapis.com/v1/places"
        self.last_error_status_code: int | None = None

    def text_search(
        self,
        query: str,
        center: GoogleMapsCoord,
        radius: int,
        fields: list[str],
    ) -> list[GoogleMapsPlaceData]:
        if not fields:
            raise ValueError("fieldsパラメータは必須です")

        try:
            response = requests.post(
                url=f"{self.base_url}:searchText",
                headers=self._headers(fields),
                json={
                    "textQuery": query,
                    "languageCode": "ja",
                    "locationBias": {
                        "circle": {
                            "center": {
                                "latitude": center.latitude,
                                "longitude": center.longitude,
                            },
                            "radius": radius,
                        }
                    },
                },
                timeout=self.TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            self.last_error_status_code = None
            return self._places_from_response(response.json().get("places", []))
        except requests.HTTPError as e:
            self._handle_http_error(e)
            return []
        except (KeyError, TypeError, requests.RequestException) as e:
            print(f"Google Maps review fetch error: {e}")
            return []

    def place_details(
        self, place_id: str, fields: list[str]
    ) -> GoogleMapsPlaceData | None:
        if not fields:
            raise ValueError("fieldsパラメータは必須です")

        try:
            response = requests.get(
                url=f"{self.base_url}/{place_id}",
                headers=self._headers(fields),
                params={"languageCode": "ja"},
                timeout=self.TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            self.last_error_status_code = None
            place = self._place_from_response(response.json())
            return place
        except requests.HTTPError as e:
            self._handle_http_error(e)
            return None
        except (KeyError, TypeError, requests.RequestException) as e:
            print(f"Google Maps review fetch error: {e}")
            return None

    def _headers(self, fields: list[str]) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": ",".join(fields),
        }

    def _places_from_response(
        self, places_data: list[dict]
    ) -> list[GoogleMapsPlaceData]:
        places = []
        for place_data in places_data:
            place = self._place_from_response(place_data)
            if place is not None:
                places.append(place)
        return places

    def _place_from_response(self, place_data: dict) -> GoogleMapsPlaceData | None:
        place_id = place_data.get("id")
        if not place_id:
            return None

        location = None
        location_data = place_data.get("location")
        if location_data:
            location = GoogleMapsCoord(
                latitude=location_data.get("latitude"),
                longitude=location_data.get("longitude"),
            )

        reviews = []
        for review_data in place_data.get("reviews", []):
            reviews.append(
                GoogleMapsReviewData(
                    text=review_data.get("text", {}).get("text"),
                    author=review_data.get("authorAttribution", {}).get("displayName"),
                    publish_time=review_data.get("publishTime"),
                    google_maps_uri=review_data.get("googleMapsUri"),
                )
            )

        return GoogleMapsPlaceData(
            place_id=place_id,
            location=location,
            name=place_data.get("displayName", {}).get("text"),
            rating=place_data.get("rating"),
            reviews=reviews,
        )

    def _handle_http_error(self, error: requests.HTTPError) -> None:
        response = error.response
        self.last_error_status_code = (
            response.status_code if response is not None else None
        )
        print(f"Google Maps review fetch HTTP error: {error}")
