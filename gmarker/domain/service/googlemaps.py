import requests

from gmarker.domain.repository.googlemaps import PlaceRepository
from gmarker.domain.valueobject.googlemaps import PlaceVO, ReviewVO, RequestBody
from gmarker.models import Place
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

        # PlaceRepositoryから全量キャッシュを取得
        place_cache = PlaceRepository.fetch_all_places()

        headers = {
            "Content-Type": "application/json",
            "X-Goog-Api-Key": self.api_key,
            "X-Goog-FieldMask": ",".join(fields),
        }

        try:
            response = requests.post(
                url=f"{self.base_url}:searchNearby",
                headers=headers,
                json=RequestBody(
                    center=center,
                    radius=radius,
                    search_types=search_types,
                ),
            )
            response.raise_for_status()
            data = response.json()
            places_data = data.get("places", [])

            # 新しいPlaceを登録
            self.extract_new_places_and_register(places_data, place_cache)

            place_vo_list: list[PlaceVO] = []
            for place_data in places_data:
                latlng = place_data.get("location")
                if latlng:
                    latlng = GoogleMapCoords(
                        latitude=latlng.get("latitude"),
                        longitude=latlng.get("longitude"),
                    )

                reviews: list[ReviewVO] = []
                review_data = place_data.get("reviews", [])
                for data in review_data:
                    reviews.append(
                        ReviewVO(
                            text=data.get("text", {}).get("text"),
                            author=data.get("authorAttribution", {}).get("displayName"),
                            publish_time=data.get("publishTime"),
                            google_maps_uri=data.get("googleMapsUri"),
                        )
                    )

                place_vo_list.append(
                    PlaceVO(
                        place=place_cache.get(place_data.get("id")),
                        location=latlng,
                        name=place_data.get("displayName", {}).get("text"),
                        rating=place_data.get("rating"),
                        reviews=reviews,
                    )
                )
            return place_vo_list

        except requests.HTTPError as e:
            print(f"An HTTP error occurred: {e}")
            return []
        except (KeyError, TypeError) as e:
            print(f"A data parsing error occurred: {e}")
            return []
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return []

    @staticmethod
    def extract_new_places_and_register(
        places_data: list[dict], place_cache: dict[str, Place]
    ) -> None:
        """
        Google Maps APIのレスポンスデータを基に、
        新しいPlaceVOを抽出し、新規Placeを登録する。

        Args:
            places_data (list[dict]): Google Maps APIのレスポンス内の施設データリスト。
            place_cache (dict[str, Place]): 既存のplace_idをキーにしたPlaceインスタンスのキャッシュ。

        Returns:
            None
        """
        new_places = []

        for place_data in places_data:
            place_id = place_data.get("id")
            if place_id in place_cache:  # 既存のPlaceはスキップ
                continue

            # 新しいPlaceVOの作成
            latlng = place_data.get("location")
            if latlng:
                latlng = GoogleMapCoords(
                    latitude=latlng.get("latitude"),
                    longitude=latlng.get("longitude"),
                )

            new_places.append(
                PlaceVO(
                    place=place_cache.get(place_id),
                    location=latlng,
                    name=place_data.get("displayName", {}).get("text"),
                    rating=place_data.get("rating"),
                    reviews=[],
                )
            )

        # 新規PlaceをDBに追加
        if new_places:
            PlaceRepository.bulk_create(new_places)
