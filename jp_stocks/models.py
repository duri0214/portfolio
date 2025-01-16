from django.db import models


class Order(models.Model):
    SIDE_CHOICES = [
        ("buy", "Buy"),
        ("sell", "Sell"),
    ]

    side = models.CharField(max_length=4, choices=SIDE_CHOICES)  # 'buy' or 'sell'
    price = models.DecimalField(max_digits=10, decimal_places=2)  # 価格
    quantity = models.PositiveIntegerField()  # 初期注文の数量
    fulfilled_quantity = models.PositiveIntegerField(default=0)  # 成立して約定した数量
    status = models.CharField(
        max_length=10, default="open"
    )  # 状態: 'open', 'fulfilled', 'cancelled'
    created_at = models.DateTimeField(auto_now_add=True)  # 注文した日時

    def __str__(self):
        return f"{self.side} {self.quantity} @ {self.price} ({self.status})"

    @property
    def remaining_quantity(self):
        """未成立の残り数量を計算"""
        return self.quantity - self.fulfilled_quantity
