from django.db import models


class NearbyPlace(models.Model):
    """
    NearbyPlaceモデルはGoogle Placesから取得した近隣の場所に関する情報を保存します。
    ユーザーが画面から登録するのは "Category"と"Pin Select"です。 "Database Insert"は主にメンテナンスのときに使います。
    """

    category = (
        models.IntegerField()
    )  # TODO: 現在時点では自位置の9の特定に必要だがバラしてフィールドにしたら？
    search_types = models.CharField(null=True, blank=True, max_length=100)
    place_id = models.CharField(null=True, blank=True, max_length=200)
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=100)
    rating = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
