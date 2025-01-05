from django.db import models


class Review(models.Model):
    location_name = models.CharField(max_length=255)  # 店舗や場所の名前
    review_text = models.TextField()  # レビュー内容
    rating = models.FloatField()  # 評価 (1-5)
    author_name = models.CharField(
        max_length=255, blank=True, null=True
    )  # レビューの著者
    review_date = models.DateTimeField()  # レビューの日付
    latitude = models.FloatField()  # 場所の緯度
    longitude = models.FloatField()  # 場所の経度
    vector = models.BinaryField(
        null=True, blank=True
    )  # ベクトル（Chromaで生成されたもの）

    class Meta:
        db_table = "reviews"  # テーブル名をわかりやすく設定
        ordering = ["-review_date"]  # デフォルトの並び順をレビュー日付の降順に設定

    def __str__(self):
        return f"{self.location_name} - {self.rating} stars"


class ConversationHistory(models.Model):
    content = models.TextField()  # 会話の内容
    timestamp = models.DateTimeField(auto_now_add=True)  # 会話が行われた日時

    class Meta:
        db_table = "conversation_history"
        ordering = ["-timestamp"]  # 新しい会話が先に表示される

    def __str__(self):
        return f"Conversation at {self.timestamp}"


class Entity(models.Model):
    name = models.CharField(max_length=100)  # エンティティの名前 (A, B, C)
    forbidden_keywords = models.TextField(
        blank=True, null=True
    )  # 禁止ワードリスト (Cが使用)
    vector = models.BinaryField(
        null=True, blank=True
    )  # ベクトル（Chromaで生成されたもの）

    class Meta:
        db_table = "entities"

    def __str__(self):
        return self.name


class Message(models.Model):
    entity = models.ForeignKey(Entity, on_delete=models.CASCADE)  # 発言したエンティティ
    conversation = models.ForeignKey(
        ConversationHistory, on_delete=models.CASCADE, related_name="messages"
    )  # 関連する会話
    message_content = models.TextField()  # 発言内容
    timestamp = models.DateTimeField(auto_now_add=True)  # 発言日時

    class Meta:
        db_table = "messages"
        ordering = ["timestamp"]  # 古いメッセージが先に表示される

    def __str__(self):
        return f"Message from {self.entity.name} at {self.timestamp}"
