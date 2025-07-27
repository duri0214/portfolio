from django.db import models

# データソースタイプの選択肢（全モデルで共通）
DATA_SOURCE_CHOICES = (
    ("google_maps_based", "Google Mapsレビューに基づく"),
    ("cloud_act_based", "Cloud Act PDFに基づく"),
    ("declining_birth_rate_based", "少子化対策PDFに基づく"),
)


class Entity(models.Model):
    """
    会話に参加するエンティティとその行動特性を定義するモデル

    このモデルは、会話参加者を定義し、それぞれに特定の思考メカニズム、制約、
    およびシステム内での動的な行動のための追加属性を提供します。

    Attributes:
        name (str): エンティティの名前（ボットやユーザーなど）
        thinking_type (str, optional): エンティティに関連付けられた思考タイプやデータソース
            選択肢:
                - "google_maps_based" (Google Mapsレビューに基づく)
                - "cloud_act_based" (Cloud Act PDFをデータソースとするRAG)
                - "declining_birth_rate_based" (少子化対策PDFをデータソースとするRAG)
                - None (User等、特定の思考タイプを持たないエンティティ)
        speed (int): 意思決定速度または応答速度。値が大きいほど応答が速くなります（値は行動頻度を表します）。
    """

    # 思考タイプの選択肢（モジュールレベルのDATA_SOURCE_CHOICESを使用）
    THINKING_TYPE_CHOICES = DATA_SOURCE_CHOICES

    name = models.CharField(max_length=100)
    thinking_type = models.CharField(
        max_length=50, choices=THINKING_TYPE_CHOICES, null=True, blank=True
    )
    speed = models.IntegerField(default=10)

    def __str__(self):
        return f"{self.name} ({self.get_thinking_type_display()})"


class RagMaterial(models.Model):
    """
    RAG (Retrieval Augmented Generation) の素材を管理するモデル

    様々なソース（Google Mapsレビュー、PDF文書など）からの情報を統一的に管理し、
    エンティティのthinking_typeに基づいて適切な情報を提供します。

    Attributes:
        material_type (str): 素材のタイプ
        source_text (str): 生のテキストデータ
        vector (binary, optional): ベクトル表現（将来的なベクトル検索用）
        entity (Entity, optional): 関連付けられたエンティティ
        metadata (JSON): 追加メタデータ（ソースタイプ固有の情報を保持）
    """

    # データソースタイプの選択肢（モジュールレベルのDATA_SOURCE_CHOICESを使用）
    MATERIAL_TYPE_CHOICES = DATA_SOURCE_CHOICES

    material_type = models.CharField(max_length=50, choices=MATERIAL_TYPE_CHOICES)
    source_text = models.TextField()
    vector = models.BinaryField(null=True, blank=True)  # 将来的なベクトル検索用
    entity = models.ForeignKey(
        "Entity",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rag_materials",
    )
    metadata = models.JSONField(default=dict, blank=True)  # ソースタイプ固有の追加情報
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.get_material_type_display()} ({self.id})"


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
