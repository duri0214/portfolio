import requests

from gmarker.domain.repository.google import PlaceRepository
from gmarker.domain.valueobject.google import PlaceVO, ReviewVO, RequestBody
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

        注意：
            [Google Cloud Platform コンソール](https://console.cloud.google.com/)でAPIキーの制限を設定する際は、ローカル開発環境（127.0.0.1）からの
            リクエストはインターネットを経由した際に送信元のグローバルIPアドレス(IPv6)に変換されます。そのため、IPアドレス制限には「グローバルIPアドレス」
            （例：240d:1a:d9:YYYY:XXXX:eab:ZZZZ:42ab）を設定してください。お使いの開発用PCで、ブラウザを開き「what is my ip」などと検索してください。

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

            return self._place_vos_from_response(response.json(), place_cache)

        except requests.HTTPError as e:
            print(f"An HTTP error occurred: {e}")
            return []
        except (KeyError, TypeError) as e:
            print(f"A data parsing error occurred: {e}")
            return []
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return []

    def text_search(
        self,
        query: str,
        center: GoogleMapsCoord,
        radius: int,
        fields: list[str],
    ) -> list[PlaceVO]:
        """
        Google Maps Places APIのText Search (New)で施設名・住所から場所を検索する。
        """
        if not fields:
            raise ValueError("fieldsパラメータは必須です")

        place_cache = PlaceRepository.fetch_all_places()

        try:
            response = requests.post(
                url=f"{self.base_url}:searchText",
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": self.api_key,
                    "X-Goog-FieldMask": ",".join(fields),
                },
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
            )
            response.raise_for_status()
            return self._place_vos_from_response(response.json(), place_cache)

        except requests.HTTPError as e:
            print(f"An HTTP error occurred: {e}")
            return []
        except (KeyError, TypeError) as e:
            print(f"A data parsing error occurred: {e}")
            return []
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return []

    def place_details(self, place_id: str, fields: list[str]) -> PlaceVO | None:
        """
        Google Maps Places APIのPlace Details (New)でレビュー本文を取得する。
        """
        if not fields:
            raise ValueError("fieldsパラメータは必須です")

        place_cache = PlaceRepository.fetch_all_places()

        try:
            response = requests.get(
                url=f"{self.base_url}/{place_id}",
                headers={
                    "Content-Type": "application/json",
                    "X-Goog-Api-Key": self.api_key,
                    "X-Goog-FieldMask": ",".join(fields),
                },
                params={"languageCode": "ja"},
            )
            response.raise_for_status()
            place_vos = self._place_vos_from_response(
                {"places": [response.json()]}, place_cache
            )
            if not place_vos:
                return None
            return place_vos[0]

        except requests.HTTPError as e:
            print(f"An HTTP error occurred: {e}")
            return None
        except (KeyError, TypeError) as e:
            print(f"A data parsing error occurred: {e}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return None

    def _place_vos_from_response(
        self, data: dict, place_cache: dict[str, Place]
    ) -> list[PlaceVO]:
        places_data = data.get("places", [])

        self.extract_new_places_and_register(places_data, place_cache)
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
            coord = None
            if latlng:
                coord = GoogleMapsCoord(
                    latitude=latlng.get("latitude"),
                    longitude=latlng.get("longitude"),
                )
            new_place_list.append(
                Place(
                    place_id=place_id,
                    name=place_data.get("displayName", {}).get("text"),
                    location=coord.to_str() if coord else None,
                    rating=place_data.get("rating"),
                )
            )

        # 一括登録処理に渡す
        if new_place_list:  # リストが空でなければ登録実行
            PlaceRepository.bulk_create(new_place_list)

            # キャッシュを更新する
            for place in new_place_list:
                place_cache[place.place_id] = place
