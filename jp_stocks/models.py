from django.db import models


class Order(models.Model):
    """
    モデル: Order

    売買注文のデータを管理するモデル。
    フィールド:
        - side: 売買の区分 ('buy' または 'sell')。
        - price: 注文の価格。
        - quantity: 初期注文の数量。
        - fulfilled_quantity: 成立して約定した数量。デフォルトは0。
        - status: 注文の状態 ('open', 'fulfilled', 'cancelled')。
        - created_at: 注文が作成された日時 (自動登録)。
    """

    SIDE_CHOICES = [
        ("buy", "Buy"),
        ("sell", "Sell"),
    ]

    side = models.CharField(max_length=4, choices=SIDE_CHOICES)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField()
    fulfilled_quantity = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=10, default="open")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.side} {self.quantity} @ {self.price} ({self.status})"

    @property
    def remaining_quantity(self):
        """未成立の残り数量を計算"""
        return self.quantity - self.fulfilled_quantity
