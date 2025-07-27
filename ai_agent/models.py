from django.db import models


class Entity(models.Model):
    """
    Represents an entity involved in conversations and defines its behavior.

    This model is used to define conversation participants, each with specific reasoning
    mechanisms, restrictions, and additional attributes for dynamic behavior in a system.

    Attributes:
        name (str): The name of the entity (e.g., a bot or user)
        thinking_type (str): The reasoning or decision-making type associated with the entity
            Choices:
                - "google_maps_based" (Google Mapsレビューに基づく)
                - "rag_based" (RAGベースの推論)
                - "ng_word_based" (NGワードに基づく制限)
        vector (binary, optional): A binary vector representation of the entity's attributes,
            commonly used for embedding-based reasoning with "rag_based"
        speed (int): The decision-making speed or response speed of the entity, where
            higher values may indicate slower response times.
    """

    THINKING_TYPE_CHOICES = (
        ("google_maps_based", "Google Mapsレビューに基づく"),  # Type A
        ("rag_based", "RAGベースの推論"),  # Type B
        ("ng_word_based", "NGワードに基づく制限"),  # Type C
    )

    name = models.CharField(max_length=100)
    thinking_type = models.CharField(
        max_length=50, choices=THINKING_TYPE_CHOICES, default="google_maps_based"
    )
    speed = models.IntegerField(default=10)

    def __str__(self):
        return f"{self.name} ({self.get_thinking_type_display()})"


class Message(models.Model):
    """
    Represents a message in a conversation.

    Attributes:
        entity (Entity): The entity that sent the message
        message_content (str): Content of the message
        created_at (datetime): Timestamp when the message was created
        updated_at (datetime): Timestamp when the message was last updated
    """

    entity = models.ForeignKey(Entity, on_delete=models.CASCADE)
    message_content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Message from {self.entity.name} at {self.created_at}"


class ActionTimeline(models.Model):
    """
    Tracks the next turn for each entity based on their speed.
    """

    entity = models.OneToOneField(Entity, on_delete=models.CASCADE)
    next_turn = models.FloatField(default=0)
    can_act = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.entity.name} - Next Turn: {self.next_turn}"


class ActionHistory(models.Model):
    entity = models.ForeignKey(Entity, on_delete=models.CASCADE)
    acted_at_turn = models.IntegerField()
    done = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.entity.name} - Turn: {self.acted_at_turn} - Done: {self.done}"


class GuardrailConfig(models.Model):
    """
    エンティティ別ガードレール設定

    Attributes:
        entity: 対象エンティティ
        forbidden_words: 禁止ワードリスト（JSON形式）
        max_input_length: 入力文字数制限
        use_openai_moderation: OpenAI Moderation APIを使用するか
        strict_mode: 厳格モード（エラー時もブロック）
    """

    entity = models.OneToOneField(Entity, on_delete=models.CASCADE)
    forbidden_words = models.JSONField(
        default=list, blank=True, help_text="禁止ワードのリスト（JSON形式）"
    )
    max_input_length = models.IntegerField(default=500, help_text="入力文字数の上限")
    use_openai_moderation = models.BooleanField(
        default=True, help_text="OpenAI Moderation APIを使用するか"
    )
    strict_mode = models.BooleanField(
        default=False, help_text="厳格モード（エラー時もブロック）"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        verbose_name = "ガードレール設定"
        verbose_name_plural = "ガードレール設定"

    def __str__(self):
        return f"{self.entity.name}のガードレール設定"
