from django.db.models import QuerySet

from gmarker.models import NearbyPlace


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
    def delete_by_category(category: int) -> bool:
        query = NearbyPlace.objects.filter(category=category)
        if query.count() > 0:
            query.delete()
            return True
        return False

    @staticmethod
    def bulk_create(objects: list[NearbyPlace]):
        NearbyPlace.objects.bulk_create(objects)

    @staticmethod
    def get_places_by_category(category: str) -> QuerySet[NearbyPlace]:
        return NearbyPlace.objects.filter(category=category)

    @classmethod
    def get_default_location(cls) -> NearbyPlace:
        return NearbyPlace.objects.get(category=cls.DEFAULT_LOCATION)
