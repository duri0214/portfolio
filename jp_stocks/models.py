from django.db import models


class Order(models.Model):
    """
    売買注文のデータを管理するモデル。
    フィールド:
        - side: 売買の区分 ('buy' または 'sell')。
        - price: 注文の価格。
        - quantity: 初期注文の数量。
        - created_at: 注文が作成された日時 (自動登録)。
    """

    SIDE_CHOICES = [
        ("buy", "Buy"),
        ("sell", "Sell"),
    ]

    side = models.CharField(max_length=4, choices=SIDE_CHOICES)
    price = models.PositiveIntegerField()
    quantity = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.side} {self.quantity} @ {self.price}"
