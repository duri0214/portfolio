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


class Staff(models.Model):
    """店舗スタッフ"""

    name = models.CharField("表示名", max_length=50)
    description = models.TextField(verbose_name="自己紹介", null=True, blank=True)
    image = models.ImageField(
        upload_to="shopping/staff",
        verbose_name="プロフィール画像",
        null=True,
        blank=True,
    )
    store = models.ForeignKey(Store, verbose_name="店舗", on_delete=models.CASCADE)
    user = models.ForeignKey(
        User, verbose_name="ログインユーザー", on_delete=models.CASCADE
    )
    created_at = models.DateTimeField("作成日時", default=timezone.now)
    updated_at = models.DateTimeField("更新日時", auto_now=True, null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "store"], name="unique_user_store"),
        ]

    def __str__(self):
        return f"{self.store.name} - {self.name}"


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
