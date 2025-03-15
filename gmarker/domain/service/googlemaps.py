import requests

from gmarker.domain.repository.googlemaps import PlaceRepository
from gmarker.domain.valueobject.googlemaps import PlaceVO, ReviewVO, RequestBody
from gmarker.models import Place
from lib.geo.valueobject.coord import GoogleMapsCoord


class GoogleMapsService:
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://places.googleapis.com/v1/places"

    def nearby_search(
        self,
        center: GoogleMapsCoord,
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

        # 【1】最初のキャッシュ取得
        # 現在のPlaceテーブルの状態をplace_idをキーにしたキャッシュとして取得。
        # ・Placeテーブルが空の場合は空のキャッシュ。
        # ・キャッシュを基にAPIから取得したデータと比較して新規登録すべきPlaceを抽出する際に使用。
        place_cache = PlaceRepository.fetch_all_places()

        try:
            response = requests.post(
                url=f"{self.base_url}:searchNearby",
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": self.api_key,
                    "X-Goog-FieldMask": ",".join(fields),
                },
                json=RequestBody(
                    center=center,
                    radius=radius,
                    search_types=search_types,
                ).to_dict(),
            )
            response.raise_for_status()

            data = response.json()
            places_data = data.get("places", [])

            # **新しいPlaceをデータベースに登録（キャッシュに存在しないものだけ）**
            self.extract_new_places_and_register(places_data, place_cache)

            # 【2】キャッシュの再取得
            # extract_new_places_and_register実行後にキャッシュを最新の状態に更新。
            # ・新規登録分も含めた完全なPlaceキャッシュを取得する。
            place_cache = PlaceRepository.fetch_all_places()

            place_vo_list: list[PlaceVO] = []
            for place_data in places_data:
                latlng = place_data.get("location")
                if latlng:
                    latlng = GoogleMapsCoord(
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
        new_place_list = []

        for place_data in places_data:
            place_id = place_data.get("id")
            if place_id in place_cache:  # 既存のPlaceはスキップ
                continue

            # 新しいPlaceを登録
            latlng = place_data.get("location")
            coords = None
            if latlng:
                coords = GoogleMapsCoord(
                    latitude=latlng.get("latitude"),
                    longitude=latlng.get("longitude"),
                )
            new_place_list.append(
                Place(
                    place_id=place_id,
                    name=place_data.get("displayName", {}).get("text"),
                    location=coords.to_str() if coords else None,
                    rating=place_data.get("rating"),
                )
            )

        # 一括登録処理に渡す
        if new_place_list:  # リストが空でなければ登録実行
            PlaceRepository.bulk_create(new_place_list)

            # キャッシュを更新する
            for place in new_place_list:
                place_cache[place.place_id] = place
