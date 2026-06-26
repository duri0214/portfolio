from pathlib import Path
from zoneinfo import ZoneInfo

from django.contrib.auth.models import User
from django.db import models

from lib.llm.valueobject.completion import RoleType
from llm_chat.domain.valueobject.completion.rag import (
    OPENAI_RAG_EMBEDDING_MODEL,
    build_openai_rag_collection_label,
    build_openai_rag_collection_name,
)
from llm_chat.domain.valueobject.completion.use_case import UseCaseType


class ChatLogs(models.Model):
    """
    LLM（大規模言語モデル）とのチャット履歴を保存するモデル。

    ユーザーの質問、システムプロンプト、AIの回答、生成された画像/音声のメタデータ、
    および実行モード（なぞなぞモード等）の状態を管理します。

    Attributes:
        user (ForeignKey): メッセージに関連付けられた Django の User インスタンス。
        role (CharField): メッセージの役割（SYSTEM, USER, ASSISTANT）。
        content (TextField): メッセージの本文（テキストまたは生成物のURL）。
        model_name (CharField): 使用された LLM のモデル名（例: gpt-4o, gpt-image-1-mini）。
        use_case_type (CharField): 使用されたユースケースタイプ（例: OpenAIGpt, Riddle, OpenAIImage）。
            ステートレスなHTTP通信において、過去の履歴から「なぞなぞ継続中か」や
            「どのユースケースを使用したか」をサーバー側で確実かつ永続的に判定するために保持します。
            具体的には、最新の履歴が `use_case_type="Riddle"` かつ終了メッセージを含まない場合に
            「継続中」とみなすロジックの根拠データとなります。
        next_riddle_state (CharField): なぞなぞセッションの状態管理用（START, WAIT_ANSWER, ...）。
        file (FileField): 生成された音声ファイルなどの保存先パス。
        created_at (DateTimeField): レコードの作成日時（自動設定）。
    """

    USE_CASE_TYPE_CHOICES = [
        (UseCaseType.OPENAI_GPT, "OpenAI GPT"),
        (UseCaseType.OPENAI_GPT_STREAMING, "OpenAI GPT Streaming"),
        (UseCaseType.GEMINI, "Gemini"),
        (UseCaseType.OPENAI_IMAGE, "OpenAI Image Generation"),
        (UseCaseType.OPENAI_TEXT_TO_SPEECH, "OpenAI Text to Speech"),
        (UseCaseType.OPENAI_SPEECH_TO_TEXT, "OpenAI Speech to Text"),
        (UseCaseType.OPENAI_RAG, "OpenAI RAG"),
        (UseCaseType.ROKUNOHE_MINUTES_RAG, "Rokunohe Minutes RAG"),
        (UseCaseType.RIDDLE, "Riddle"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=9,
        choices=[(x.name, x.value) for x in RoleType],
    )
    content = models.TextField()
    model_name = models.CharField(max_length=50, null=True, blank=True)
    use_case_type = models.CharField(
        max_length=50,
        choices=USE_CASE_TYPE_CHOICES,
        default=UseCaseType.OPENAI_GPT,
        help_text="使用されたユースケースタイプ（例: OpenAIGpt, Riddle, OpenAIImage）",
    )
    riddle_scores = models.JSONField(
        null=True,
        blank=True,
        help_text="なぞなぞの単問評価スコア（correctness, reasoning, creativity, rebuttal）",
    )
    next_riddle_state = models.CharField(
        max_length=100,
        null=True,
        blank=True,
        help_text="なぞなぞセッションの状態管理用（START, WAIT_ANSWER, ...）",
    )
    file = models.FileField(upload_to="llm_chat/audios/", null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def to_message_dto(self) -> "MessageDTO":
        """
        このエンティティを MessageDTO に変換します。
        """
        from llm_chat.domain.valueobject.completion.chat import MessageDTO

        return MessageDTO(
            user=self.user,
            role=RoleType(self.role),
            content=self.content,
            model_name=self.model_name,
            use_case_type=self.use_case_type,
            next_riddle_state=self.next_riddle_state,
            riddle_scores=self.riddle_scores,
            file_path=self.file.url if self.file else None,
            file_name=self.file.name if self.file else None,
        )


class RiddleQuestion(models.Model):
    """
    なぞなぞの問題と正解を管理するモデル。

    Attributes:
        question_text (CharField): なぞなぞの問題文。
        answer_text (TextField): なぞなぞの正解。
        order (IntegerField): 出題順序。
        created_at (DateTimeField): レコードの作成日時。
    """

    question_text = models.CharField(max_length=255, verbose_name="問題文", unique=True)
    answer_text = models.TextField(verbose_name="正解")
    order = models.IntegerField(verbose_name="出題順序", default=0, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "なぞなぞ問題"
        verbose_name_plural = "なぞなぞ問題一覧"
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"{self.order}: {self.question_text[:20]}..."


class OpenAIRagPdf(models.Model):
    """
    OpenAI RAGで利用するPDFファイルを管理するモデル。

    固定サンプルPDFを暗黙に使うのではなく、ユーザーが登録したPDFを
    チャット画面で明示的に選択できるようにするためのメタデータを保持します。

    Attributes:
        display_name: チャット画面や管理画面に表示するPDF名。
        collection_name: Chroma DB上の物理collection名。
        is_active: チャット画面の選択肢として表示するかどうか。
        imported_at: Vector DBへの登録が完了した日時。
        created_at: レコードの作成日時。
    """

    display_name = models.CharField("表示名", max_length=255)
    collection_name = models.CharField(
        "物理collection名", max_length=63, unique=True, null=True, blank=True
    )
    is_active = models.BooleanField("有効", default=True)
    imported_at = models.DateTimeField("Vector DB登録日時", null=True, blank=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        verbose_name = "OpenAI RAG PDF"
        verbose_name_plural = "OpenAI RAG PDF一覧"
        ordering = ["-created_at"]

    def __str__(self):
        return self.display_name

    def assign_collection_name(self) -> None:
        if not self.id:
            raise ValueError("collection_name requires a saved OpenAIRagPdf ID")
        if self.collection_name:
            return

        self.collection_name = build_openai_rag_collection_name(self.id)
        self.save(update_fields=["collection_name"])

    @property
    def collection_label(self) -> str:
        suffix = Path(self.display_name).suffix.lstrip(".")
        source_extension_label = suffix.upper() if suffix else "UNKNOWN"
        imported_at = "未登録"
        if self.imported_at:
            imported_at = (
                self.imported_at.astimezone(ZoneInfo("Asia/Tokyo"))
                .replace(microsecond=0)
                .strftime("%Y-%m-%d %H:%M:%S")
            )
        return build_openai_rag_collection_label(
            source_extension_label=source_extension_label,
            source_name=self.display_name,
            embedding_model=OPENAI_RAG_EMBEDDING_MODEL,
            imported_at=imported_at,
        )
