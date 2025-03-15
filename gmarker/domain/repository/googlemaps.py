from collections import defaultdict

from django.db import OperationalError, IntegrityError

from gmarker.domain.valueobject.googlemaps import PlaceVO
from gmarker.models import NearbyPlace, Place, PlaceReview
from lib.geo.valueobject.coords import GoogleMapsCoord


class PlaceRepository:
    @staticmethod
    def fetch_existing_place_ids(place_ids: list[str]) -> set[str]:
        return set(
            Place.objects.filter(place_id__in=place_ids).values_list(
                "place_id", flat=True
            )
        )

    @staticmethod
    def bulk_create(new_place_list: list[Place]):
        if new_place_list:
            Place.objects.bulk_create(new_place_list)

    @staticmethod
    def fetch_all_places() -> dict[str, Place]:
        """
        全ての Place データを取得し、辞書形式で返却します。

        Returns:
            dict[str, Place]: place_id をキー、Place インスタンスを値とする辞書。
        """
        return {place.place_id: place for place in Place.objects.all()}


class NearbyPlaceRepository:
    """
    近隣場所情報を管理するリポジトリクラスです。
    カテゴリーフィールドは以下の値を持ちます:
        1 = "Category": 具体的なカテゴリで検索され、登録される場所
        2 = "Preset": あらかじめDBに登録された場所
        9 = "Default Location": デフォルトの場所（マップを初期表示したときの中心）
    """

    CATEGORY_SEARCH = 1
    PRESETS = 2
    DEFAULT_LOCATION = 9

    @staticmethod
    def find_places_with_reviews_by_category(category: int, review_limit: int = 5):
        """
        指定したカテゴリのNearbyPlaceと、それに関連付けられたPlaceReviewを取得。

        Args:
            category (int): 対象とするNearbyPlaceのカテゴリ
            review_limit (int): 各Placeあたり取得するレビューの最大数

        Returns:
            list[dict]: NearbyPlace情報と各Placeのレビュー情報を含むリスト
        """
        nearby_places = NearbyPlace.objects.filter(category=category)
        place_data = []

        for nearby_place in nearby_places:
            lat, lng = map(float, nearby_place.place.location.split(","))
            reviews = PlaceReviewRepository.get_reviews_for_place(
                nearby_place.place, limit=review_limit
            )

            place_data.append(
                {
                    "location": {
                        "lat": lat,
                        "lng": lng,
                    },
                    "name": nearby_place.place.name,
                    "place_id": nearby_place.place.place_id,
                    "rating": nearby_place.place.rating,
                    "reviews": reviews,
                }
            )

        return place_data

    @staticmethod
    def delete_by_category(category: int) -> bool:
        query = NearbyPlace.objects.filter(category=category)
        if query.count() > 0:
            query.delete()
            return True
        return False

    @staticmethod
    def bulk_create(new_nearby_place_list: list[NearbyPlace]):
        NearbyPlace.objects.bulk_create(new_nearby_place_list)

    @classmethod
    def get_default_location(cls) -> NearbyPlace | None:
        try:
            return NearbyPlace.objects.get(category=cls.DEFAULT_LOCATION)
        except NearbyPlace.DoesNotExist:
            return None

    @staticmethod
    def handle_search_code(
        category: int, search_types: str, place_vo_list: list[PlaceVO]
    ):
        """
        検索結果に基づいてNearbyPlaceおよびPlaceを管理するメソッド。

        Args:
            category (int): カテゴリ
            search_types (str): 検索タイプ
            place_vo_list (list[PlaceVO]): 検索結果としての場所データ
        """
        NearbyPlaceRepository.delete_by_category(category)
        nearby_places = [
            NearbyPlace(
                category=category,
                search_types=search_types,
                place=Place.objects.get(place_id=place_vo.place.place_id),
            )
            for place_vo in place_vo_list
        ]
        NearbyPlaceRepository.bulk_create(nearby_places)

        for place_vo in place_vo_list:
            place_reviews = [
                PlaceReview(
                    review_text=review.text,
                    author=review.author,
                    publish_time=review.publish_time,
                    google_maps_uri=review.google_maps_uri,
                    place=place_vo.place,
                )
                for review in place_vo.reviews
            ]
            PlaceReviewRepository.bulk_create(place_reviews)

    @staticmethod
    def upsert_default_location(
        coords: GoogleMapsCoord, name: str = "My Center Location"
    ) -> NearbyPlace:
        """
        category=9 (デフォルトの場所) のアップサートを行います。

        Args:
            coords (GoogleMapsCoord): GoogleMapsCoordオブジェクト（緯度と経度）
            name (str): レコード作成時のデフォルト名（任意）

        Returns:
            NearbyPlace: 更新または作成されたレコード
        """
        location_str = coords.to_str()  # 座標を文字列化
        # アップサート処理
        nearby_place, created = NearbyPlace.objects.update_or_create(
            category=9,  # 固定のカテゴリ
            defaults={
                "location": location_str,  # locationを更新
                "name": name,  # 新規作成時のデフォルト名
            },
        )
        return nearby_place


class PlaceReviewRepository:
    @staticmethod
    def get_reviews_for_place(place, limit: int = 5):
        """
        指定したPlaceに関連付けられたレビューを取得（最新順）。

        Args:
            place (Place): 対象のPlace
            limit (int): 最大取得件数

        Returns:
            list[dict]: レビュー情報を辞書形式で格納したリスト
        """
        reviews = PlaceReview.objects.filter(place=place).order_by("-publish_time")[
            :limit
        ]
        return [
            {
                "author": review.author,
                "review_text": review.review_text,
                "publish_time": (
                    review.publish_time.strftime("%Y-%m-%d %H:%M:%S")
                    if review.publish_time
                    else None
                ),
            }
            for review in reviews
        ]

    @staticmethod
    def bulk_create(new_place_review_list: list[PlaceReview]):
        # PlaceReviewのキャッシュを事前に作成
        existing_reviews = PlaceReview.objects.values(
            "place_id", "author", "id", "review_text"
        )
        existing_reviews_map = {
            (review["place_id"], review["author"]): review
            for review in existing_reviews
        }

        # 重複エラーを格納する辞書 (place名がキーで、authorのリストが値)
        duplicate_errors = defaultdict(list)

        for review in new_place_review_list:
            try:
                # 同じplaceの同じauthorのレビューがあったらupdateにする
                existing_review = existing_reviews_map.get(
                    (review.place.place_id, review.author)
                )

                if existing_review:
                    PlaceReview.objects.filter(id=existing_review["id"]).update(
                        review_text=review.review_text
                    )
                else:
                    review.save()

            except IntegrityError as e:
                if "Duplicate entry" in str(e):
                    duplicate_errors[review.place.name].append(review.author)
                else:
                    print(f"Integrity Error! Review: {review}: {e}")

            except OperationalError as e:
                print(f"Error occurred while processing review: {review}: {e}")

            except Exception as e:
                print(f"Unexpected error while processing review: {review}: {e}")

        # 重複エラーをまとめて出力
        for place, authors in duplicate_errors.items():
            print(f"Duplicate Error! Place: {place} | Authors: {authors}")
