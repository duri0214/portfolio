from django.db import models


class NearbyPlace(models.Model):
    """
    NearbyPlaceモデルはGoogle Placesから取得した近隣の場所に関する情報を保存します。

    code9は自拠点を示します。
    カテゴリーフィールドは以下の値を持ます:
        1 = "Category": 具体的なカテゴリーで検索され、登録された場所
        2 = "Pin Select": Googleマップ上でピンを選んで登録した場所
        3 = "Database Insert": データベースから直接挿入された情報
        9 = "Default Location": デフォルト位置（マップを初期表示したときの中心）

    主にユーザーが画面から登録するのは "Category"と"Pin Select"です。 "Database Insert"は主にメンテナンスのときに使います。
    """

    CATEGORY_SEARCH = 1
    PIN_SELECT = 2
    DATABASE_INSERT = 3
    DEFAULT_LOCATION = 9

    # TODO: このフィールドは「必要」なのか？
    category = models.IntegerField(
        choices=[
            (CATEGORY_SEARCH, "Category"),
            (PIN_SELECT, "Pin Select"),
            (DATABASE_INSERT, "Database Insert"),
            (DEFAULT_LOCATION, "Default Location"),
        ]
    )
    search_word = models.CharField(null=True, blank=True, max_length=100)
    place_id = models.CharField(null=True, blank=True, max_length=200)
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)


class CategorySearchMaster(models.Model):
    """
    CategorySearchMaster is a model that serves as a Master table for category search.

    Fields:
        code (CharField): The unique code associated with each category.
        name (CharField): The name of the category associated with each unique code.

    Sample data:
        "1A", "ラーメン"
        "1B", "洋食"
        "1C", "和食"

    This model is used to fetch the category name using the code.
    """

    code = models.CharField(primary_key=True, max_length=2)
    name = models.CharField(max_length=100)
