from urllib.parse import quote

import requests

from gmarker.domain.valueobject.googlemaps import PlacePhoto, PlaceVO
from lib.geo.valueobject.coords import GoogleMapCoords


class GoogleMapsService:
    def __init__(self, api_key: str):
        self.api_key = api_key

    def nearby_search(
        self, keyword: str, center: GoogleMapCoords, types: str, radius: int
    ) -> list[PlaceVO]:
        """
        Google Maps Places API を使用して、指定された場所の周辺で特定のタイプの施設を検索します。

        Args:
            keyword (str): 検索キーワード（例：レストラン）
            center (GoogleMapCoords): 検索の中心となる座標
            types (str): 検索する施設のタイプ
            radius (int): 検索範囲の半径（メートル）

        Returns:
            list[PlaceVO]: 検索結果の施設リスト。以下の情報を持つPlaceVOオブジェクトのリストを返します。

        Raises:
            requests.HTTPError: リクエストが成功的なステータスコード（200 OK）を返さなかった場合に発生します。
            Exception: 上記以外の未知のエラーが発生した場合に発生します。
        """

        urlencoded_keyword = quote(keyword)
        url = (
            "https://maps.googleapis.com/maps/api/place/nearbysearch/json?"
            f"location={center.to_str()}&radius={radius}&type={types}&keyword={urlencoded_keyword}&"
            f"key={self.api_key}"
        )

        try:
            response = requests.get(url)
            response.raise_for_status()

            results = response.json().get("results", [])
            places = []
            for result in results:
                latlng = GoogleMapCoords(
                    latitude=result["geometry"]["location"]["lat"],
                    longitude=result["geometry"]["location"]["lng"],
                )

                photos = []
                for photo in result.get("photos", []):
                    photos.append(
                        PlacePhoto(
                            height=photo.get("height"),
                            width=photo.get("width"),
                            html_attributions=photo.get("html_attributions", []),
                            photo_reference=photo.get("photo_reference"),
                        )
                    )

                places.append(
                    PlaceVO(
                        search_word=keyword,
                        place_id=result.get("place_id"),
                        name=result.get("name"),
                        location=latlng,
                        photos=photos,
                        detail=None,  # TODO: 後でPlaceDetailVOに更新してください
                    )
                )

            return places

        except requests.HTTPError as e:
            print(f"An HTTP error occurred: {e}")
            return []
        except Exception as e:
            print(f"An error occurred: {e}")
            return []

    def get_place_details(self, place_vo: PlaceVO) -> PlaceVO | None:
        fields = [
            "geometry",
            "name",
            "photo",
            "place_id",
            "rating",
            "review",
            "url",
        ]
        fields_str = ",".join(fields)
        url = (
            f"https://maps.googleapis.com/maps/api/place/details/json?"
            f"place_id={place_vo.place_id}&fields={fields_str}&key={self.api_key}"
        )

        try:
            response = requests.get(url)
            response.raise_for_status()

            result = response.json()["result"]

            # Update the PlaceVO object with new data
            place_vo.name = result.get("name")
            place_photos = []
            for photo in result.get("photos", []):
                place_photos.append(
                    PlacePhoto(
                        height=photo["height"],
                        width=photo["width"],
                        html_attributions=photo["html_attributions"],
                        photo_reference=photo["photo_reference"],
                    )
                )
            place_vo.photos = place_photos
            place_vo.location = GoogleMapCoords(
                latitude=result["geometry"]["location"]["lat"],
                longitude=result["geometry"]["location"]["lng"],
            )

            # Update the detail value here when available TODO: reviewsの取得
            # place_vo.detail = PlaceDetailVO(...)

            return place_vo
        except requests.HTTPError as e:
            print(f"An HTTP error occurred: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")

        return None
