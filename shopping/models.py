from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class Store(models.Model):
    """店舗"""

    name = models.CharField("店名", max_length=255)
    created_at = models.DateTimeField("作成日時", default=timezone.now)
    updated_at = models.DateTimeField("更新日時", auto_now=True, null=True, blank=True)

    def __str__(self):
        return self.name


class StorePlanningDataSourceSnapshot(models.Model):
    """
    出店計画で参照する e-Stat 人口CSVの取得・集計スナップショット。

    Attributes:
        source_key: データソースを識別するキー。
        display_name: 画面に表示するデータソース名。
        source_url: e-Statの統計表を確認できる公開URL。
        status: 取得・利用状態。
        data_period: e-Statデータの対象期間。
        source_updated_at: e-Statが公表している更新日時。
        fetched_at: アプリがローカルDBへ保存した日時。
        raw_data: e-Stat CSVから保存した集計値とメタ情報。市区町村コード、
            町丁字コード、地域階層レベルなど、e-Stat CSVの地域区分列も
            保存値のまま保持する。地域階層レベルは、総務省統計局
            「令和2年国勢調査 調査結果の利用案内」に従い、
            1=市区町村単位、2=字・町名（異なる字・丁目の地域を含まないもの）、
            3=大字・町名が同じ字・丁目の合計、4=字・丁目単位を表す。
    """

    source_key = models.CharField("データソースキー", max_length=100, unique=True)
    display_name = models.CharField("表示名", max_length=255)
    source_url = models.URLField("提供元URL", max_length=500)
    status = models.CharField("取得状態", max_length=100)
    data_period = models.CharField("データ時点", max_length=255, blank=True)
    source_updated_at = models.DateTimeField("提供元更新日時", null=True, blank=True)
    fetched_at = models.DateTimeField("アプリ取得日時", default=timezone.now)
    raw_data = models.JSONField("取得メタデータ", default=dict, blank=True)

    def __str__(self):
        return self.display_name


class StorePlanningTargetStore(models.Model):
    """
    出店計画画面で選択対象にするサンプル店舗候補。

    Attributes:
        slug: URLパラメータと保存キーに使う識別子。
        name: 画面に表示する店舗名。
        address: 店舗または候補地の住所。
        latitude: Google Mapsリンクに使う緯度。
        longitude: Google Mapsリンクに使う経度。
        city_code: e-Stat CSVの市区町村コード。
        town_code: e-Stat CSVの町丁字コード。
        population_area: 人口集計に使う町丁字名。
        large_area_name: e-Stat CSVの大字・町名。
        small_area_name: e-Stat CSVの字・丁目名。
        area_hierarchy_level: e-Stat CSVの地域階層レベル。
        is_active: 出店計画画面の選択肢として表示するかどうか。
        created_at: 作成日時。
        updated_at: 更新日時。
    """

    slug = models.SlugField("店舗キー", max_length=100, unique=True)
    name = models.CharField("店舗名", max_length=255)
    address = models.CharField("住所", max_length=500)
    latitude = models.FloatField("緯度", null=True, blank=True)
    longitude = models.FloatField("経度", null=True, blank=True)
    city_code = models.CharField("e-Stat市区町村コード", max_length=10)
    town_code = models.CharField("e-Stat町丁字コード", max_length=10)
    population_area = models.CharField("人口集計地域", max_length=255)
    large_area_name = models.CharField("大字・町名", max_length=100, blank=True)
    small_area_name = models.CharField("字・丁目名", max_length=100, blank=True)
    area_hierarchy_level = models.CharField("地域階層レベル", max_length=1, default="4")
    is_active = models.BooleanField("表示対象", default=True)
    created_at = models.DateTimeField("作成日時", default=timezone.now)
    updated_at = models.DateTimeField("更新日時", auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class StorePlanningGoogleMapsReview(models.Model):
    """
    出店計画の店舗候補ごとに取得した Google Maps レビュー。

    Attributes:
        target_store: 出店計画の対象店舗候補。
        google_place_id: Google Maps の Place ID。
        place_name: レビュー対象施設名。
        latitude: レビュー対象施設の緯度。
        longitude: レビュー対象施設の経度。
        rating: レビュー対象施設の Google Maps rating。
        review_text: レビュー本文。
        author: レビュー投稿者名。
        publish_time: レビュー公開日時。
        google_maps_uri: レビューまたは施設の Google Maps URL。
        fetched_at: アプリがレビューを取得した日時。
        created_at: 作成日時。
        updated_at: 更新日時。
    """

    target_store = models.ForeignKey(
        StorePlanningTargetStore,
        verbose_name="出店計画対象店舗",
        on_delete=models.CASCADE,
        related_name="google_maps_reviews",
    )
    target_store_slug = models.SlugField(
        "店舗キー", max_length=100, blank=True, db_index=True
    )
    google_place_id = models.CharField("Google Place ID", max_length=200)
    place_name = models.CharField("施設名", max_length=255)
    latitude = models.FloatField("緯度")
    longitude = models.FloatField("経度")
    rating = models.FloatField("Google Maps rating", null=True, blank=True)
    review_text = models.TextField("レビュー本文", blank=True)
    author = models.CharField("投稿者", max_length=200, blank=True)
    publish_time = models.DateTimeField("レビュー公開日時", null=True, blank=True)
    google_maps_uri = models.URLField("Google Maps URL", max_length=500, blank=True)
    fetched_at = models.DateTimeField("アプリ取得日時", default=timezone.now)
    created_at = models.DateTimeField("作成日時", default=timezone.now)
    updated_at = models.DateTimeField("更新日時", auto_now=True, null=True, blank=True)

    class Meta:
        ordering = ["-publish_time", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["target_store_slug", "google_place_id", "author"],
                name="unique_store_planning_google_review_author",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.target_store_slug and self.target_store_id:
            self.target_store_slug = self.target_store.slug
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.target_store.name}: {self.place_name} ({self.author})"


class UserAttribute(models.Model):
    """
    ショッピングアプリ特有のユーザー属性。

    - Django 標準の auth.User と 1:1 で紐づく（認証や氏名・メール等は auth.User を参照）
    - ショッピングドメイン固有の情報を保持（ロール、住所、ランクなど）

    Attributes:
        - user (OneToOneField): ユーザ
        - role (CharField): ロール (STAFF/CUSTOMER)
        - nickname (CharField): 表示名
        - description (TextField): 自己紹介（スタッフ用）
        - image (ImageField): プロフィール画像
        - store (ForeignKey): 所属店舗（スタッフ用）
        - address (TextField): 配送先等の住所情報
        - remark (TextField): 備考
        - created_at (DateTimeField): 作成日時
        - updated_at (DateTimeField): 更新日時
    """

    class Role(models.TextChoices):
        """
        ロール定義:
        - STAFF: 店舗スタッフ
        - CUSTOMER: 一般購入者
        """

        STAFF = "staff", "店舗スタッフ"
        CUSTOMER = "customer", "一般購入者"

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="shopping_profile",
        verbose_name="ユーザ",
    )
    role = models.CharField(
        max_length=20,
        choices=Role,
        verbose_name="ロール",
    )
    nickname = models.CharField("表示名", max_length=50, null=True, blank=True)
    description = models.TextField(verbose_name="自己紹介", null=True, blank=True)
    image = models.ImageField(
        upload_to="shopping/profile",
        verbose_name="プロフィール画像",
        null=True,
        blank=True,
    )
    store = models.ForeignKey(
        Store,
        on_delete=models.SET_NULL,
        verbose_name="所属店舗",
        null=True,
        blank=True,
        related_name="staff_profiles",
    )
    address = models.TextField(verbose_name="住所", null=True, blank=True)
    remark = models.TextField(verbose_name="備考", null=True, blank=True)
    created_at = models.DateTimeField("作成日時", default=timezone.now)
    updated_at = models.DateTimeField("更新日時", auto_now=True, null=True, blank=True)

    def __str__(self):
        return self.nickname or self.user.username


class Product(models.Model):
    """
    商品
    """

    code = models.CharField("商品コード", max_length=200)
    name = models.CharField("商品名", max_length=200)
    price = models.IntegerField("金額", default=0)
    description = models.TextField("説明")
    picture = models.ImageField("商品写真", upload_to="shopping/")
    created_at = models.DateTimeField("作成日時", default=timezone.now)
    updated_at = models.DateTimeField("更新日時", auto_now=True, null=True, blank=True)

    def __str__(self):
        return f"{self.code}: {self.name}"


class BuyingHistory(models.Model):
    """購入履歴"""

    # 支払い状態の定数
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    REFUNDED = "refunded"

    # 選択肢のリスト
    PAYMENT_STATUS_CHOICES = [
        (PENDING, "支払い待ち"),
        (COMPLETED, "支払い完了"),
        (FAILED, "支払い失敗"),
        (REFUNDED, "返金済み"),
    ]

    product = models.ForeignKey(
        Product, verbose_name="商品名", on_delete=models.PROTECT
    )
    user = models.ForeignKey(User, verbose_name="購入者", on_delete=models.PROTECT)
    price = models.IntegerField("商品単価", default=0)
    quantity = models.IntegerField("購入数量", default=1)
    tax_rate = models.DecimalField("税率", max_digits=5, decimal_places=2, default=0.10)
    stripe_id = models.CharField("Stripe決済ID", max_length=200)
    payment_status = models.CharField(
        "支払い状態",
        max_length=20,
        choices=PAYMENT_STATUS_CHOICES,
        default=PENDING,
    )
    shipped = models.BooleanField("発送済み", default=False)
    created_at = models.DateTimeField("作成日時", default=timezone.now)
    updated_at = models.DateTimeField("更新日時", auto_now=True, null=True, blank=True)

    def __str__(self):
        return f"{self.product.name} - {self.user.username} ({self.created_at.strftime('%Y-%m-%d')})"

    @property
    def subtotal(self) -> int:
        """税抜きの小計を計算します"""
        return self.price * self.quantity

    @property
    def tax_amount(self) -> int:
        """税額を計算します"""
        return int(self.subtotal * float(self.tax_rate))

    @property
    def total_amount(self) -> int:
        """合計金額（税込）を計算します"""
        return self.subtotal + self.tax_amount
