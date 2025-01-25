from django.db.models import QuerySet

from gmarker.domain.valueobject.googlemaps import PlaceVO
from gmarker.models import NearbyPlace, Place
from lib.geo.valueobject.coords import GoogleMapCoords


class PlaceRepository:
    @staticmethod
    def fetch_existing_place_ids(place_ids: list[str]) -> set[str]:
        return set(
            Place.objects.filter(place_id__in=place_ids).values_list(
                "place_id", flat=True
            )
        )

    @staticmethod
    def bulk_create(new_places: list[PlaceVO]):
        place_instances = [
            Place(
                place_id=place.place_id,
                name=place.name,
                location=place.location.to_str(),
                rating=place.rating,
            )
            for place in new_places
        ]
        if place_instances:
            Place.objects.bulk_create(place_instances)


class NearbyPlaceRepository:
    """
    近隣場所情報を管理するリポジトリクラスです。
    カテゴリーフィールドは以下の値を持ちます:
        1 = "Category": 具体的なカテゴリで検索され、登録される場所
        2 = "Pin Select": Googleマップ上でピンを選び、登録した場所
        3 = "Database Insert": データベースから直接挿入される情報
        9 = "Default Location": デフォルトの場所（マップを初期表示したときの中心）
    ここで、"Category"と"Pin Select"は主にユーザーが画面から登録し、"Database Insert"は主にメンテナンス時に使用されます。
    """

    CATEGORY_SEARCH = 1
    PIN_SELECT = 2
    DATABASE_INSERT = 3
    DEFAULT_LOCATION = 9

    @staticmethod
    def find_by_category(category: int) -> QuerySet:
        return NearbyPlace.objects.filter(category=category)

    @staticmethod
    def delete_by_category(category: int) -> bool:
        query = NearbyPlace.objects.filter(category=category)
        if query.count() > 0:
            query.delete()
            return True
        return False

    @staticmethod
    def bulk_create(objects: list[NearbyPlace]):
        NearbyPlace.objects.bulk_create(objects)

    @classmethod
    def get_default_location(cls) -> NearbyPlace | None:
        try:
            return NearbyPlace.objects.get(category=cls.DEFAULT_LOCATION)
        except NearbyPlace.DoesNotExist:
            return None

    @staticmethod
    def handle_search_code(category: int, search_types: str, places: list[PlaceVO]):
        """
        検索結果に基づいてNearbyPlaceおよびPlaceを管理するメソッド。

        Args:
            category (int): カテゴリ
            search_types (str): 検索タイプ
            places (list[PlaceVO]): 検索結果としての場所データ
        """
        NearbyPlaceRepository.delete_by_category(category)
        if places:
            place_ids = [place.place_id for place in places]
            existing_place_ids = PlaceRepository.fetch_existing_place_ids(place_ids)
            new_places = [
                place for place in places if place.place_id not in existing_place_ids
            ]
            PlaceRepository.bulk_create(new_places)

            nearby_places = [
                NearbyPlace(
                    category=category,
                    search_types=search_types,
                    place=Place.objects.get(place_id=place.place_id),
                )
                for place in places
            ]
            NearbyPlaceRepository.bulk_create(nearby_places)

    @staticmethod
    def upsert_default_location(
        coords: GoogleMapCoords, name: str = "My Center Location"
    ) -> NearbyPlace:
        """
        category=9 (デフォルトの場所) のアップサートを行います。

        Args:
            coords (GoogleMapCoords): GoogleMapCoordsオブジェクト（緯度と経度）
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
