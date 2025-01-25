from django.db import models


class Place(models.Model):
    """
    Placeモデルは、NearbyPlaceやPlaceReviewから参照される基幹モデルです。
    Google Place IDをユニークキーとして使用し、その他の場所情報も保持します。
    """

    place_id = models.CharField(max_length=200, unique=True)
    name = models.CharField(max_length=200)
    location = models.CharField(max_length=100)
    rating = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return f"{self.name} ({self.place_id})"


class NearbyPlace(models.Model):
    """
    NearbyPlaceモデルはGoogle Placesから取得した近隣の場所に関する情報を保存します。
    ユーザーが画面から登録するのは "Category"と"Pin Select"です。 "Database Insert"は主にメンテナンスのときに使います。
    """

    category = (
        models.IntegerField()
    )  # TODO: 現在時点では自位置の9の特定に必要だがバラしてフィールドにしたら？
    search_types = models.CharField(null=True, blank=True, max_length=100)
    place = models.ForeignKey(Place, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return f"{self.place.name} - Category: {self.category}"


class PlaceReview(models.Model):
    review_text = models.TextField(null=True, blank=True)
    author = models.CharField(max_length=200, null=True, blank=True)
    publish_time = models.DateTimeField(null=True, blank=True)
    google_maps_uri = models.URLField(null=True, blank=True)  # GoogleマップのURI
    place = models.ForeignKey(Place, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return f"Review by {self.author} for {self.place.name}"
