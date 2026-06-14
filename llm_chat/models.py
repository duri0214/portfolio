from django.contrib.auth.models import User
from django.db import models

from lib.llm.valueobject.completion import RoleType
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


class RokunoheMinuteThemeAnalysisJob(models.Model):
    """
    六戸町会議録テーマ分析の実行単位を管理するモデル。

    ここでいう「ジョブ」は、1チャンクや1クラスタではなく、管理画面から
    テーマ分析ボタンを1回押したときに始まる分析全体の束です。たとえば
    1,369件のChromaチャンクを対象にした実行なら、1,369件それぞれにジョブが
    作られるのではなく、1つのジョブが「1,369件をまとめて処理中/完了/失敗」
    という状態を持ちます。

    チャンクごとの `10/1369` のような進捗はサーバログで追跡する運用です。
    このモデルには現在処理中のチャンク番号や個別チャンクのrunning状態は保存せず、
    実行全体の最終状態と、完了後に画面表示で使う集計値だけを残します。

    Attributes:
        status: 分析実行全体の状態。チャンク単位の状態ではない。
        requested_cluster_count: 実行時に要求したクラスタ数。
        actual_cluster_count: 入力件数に応じて実際に生成したクラスタ数。
        chunk_count: 分析対象になったChromaチャンク数。完了時に実績値を保存する。
        llm_model_name: テーマ候補と代表ラベル生成に使ったLLMモデル名。
        error_message: 失敗時のエラー内容。
        created_at: レコードの作成日時。
        completed_at: 分析完了日時。
    """

    STATUS_RUNNING = "running"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = [
        (STATUS_RUNNING, "実行中"),
        (STATUS_COMPLETED, "完了"),
        (STATUS_FAILED, "失敗"),
    ]

    status = models.CharField(
        verbose_name="実行状態",
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_RUNNING,
    )
    requested_cluster_count = models.PositiveIntegerField(
        verbose_name="要求クラスタ数",
        default=50,
    )
    actual_cluster_count = models.PositiveIntegerField(
        verbose_name="実クラスタ数",
        default=0,
    )
    chunk_count = models.PositiveIntegerField(
        verbose_name="分析対象チャンク数",
        default=0,
    )
    llm_model_name = models.CharField(
        verbose_name="LLMモデル名",
        max_length=50,
        blank=True,
    )
    error_message = models.TextField(
        verbose_name="エラーメッセージ",
        blank=True,
    )
    created_at = models.DateTimeField(verbose_name="作成日時", auto_now_add=True)
    completed_at = models.DateTimeField(
        verbose_name="完了日時",
        null=True,
        blank=True,
    )

    class Meta:
        db_table = "llm_chat_rokunohe_minute_theme_analysis_job"
        verbose_name = "六戸町会議録テーマ分析ジョブ"
        verbose_name_plural = "六戸町会議録テーマ分析ジョブ一覧"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Rokunohe theme analysis job #{self.pk}: {self.status}"


class RokunoheMinuteThemeCluster(models.Model):
    """
    六戸町会議録テーマ分析で生成されたクラスタを管理するモデル。

    分析ジョブが対象チャンク全体をK-meansで束ねたあとに作る、テーマ単位の
    結果行です。ジョブの途中状態を表す行ではなく、ビューアや一覧で
    「この実行ではどんなテーマ群ができたか」を読むための永続化結果です。

    Attributes:
        job: このクラスタを生成した分析ジョブ。
        cluster_index: K-meansが割り当てたクラスタ番号。
        label: LLMが命名した代表テーマ名。
        representative_chunk_id: 代表チャンクのChroma ID。
        chunk_count: クラスタに属するチャンク数。
        character_count: クラスタに属する本文文字数。
        pdf_count: クラスタに含まれるPDF数。
        source_date_from: クラスタ内の最古source_date。
        source_date_to: クラスタ内の最新source_date。
        created_at: レコードの作成日時。
    """

    job = models.ForeignKey(
        RokunoheMinuteThemeAnalysisJob,
        verbose_name="分析ジョブ",
        related_name="clusters",
        on_delete=models.CASCADE,
    )
    cluster_index = models.PositiveIntegerField(verbose_name="クラスタ番号")
    label = models.CharField(verbose_name="代表テーマ名", max_length=255)
    representative_chunk_id = models.CharField(
        verbose_name="代表チャンクID",
        max_length=512,
        blank=True,
    )
    chunk_count = models.PositiveIntegerField(verbose_name="チャンク数", default=0)
    character_count = models.PositiveIntegerField(verbose_name="文字数", default=0)
    pdf_count = models.PositiveIntegerField(verbose_name="PDF数", default=0)
    source_date_from = models.CharField(
        verbose_name="開始日",
        max_length=8,
        blank=True,
    )
    source_date_to = models.CharField(
        verbose_name="終了日",
        max_length=8,
        blank=True,
    )
    created_at = models.DateTimeField(verbose_name="作成日時", auto_now_add=True)

    class Meta:
        db_table = "llm_chat_rokunohe_minute_theme_cluster"
        verbose_name = "六戸町会議録テーマクラスタ"
        verbose_name_plural = "六戸町会議録テーマクラスタ一覧"
        unique_together = ("job", "cluster_index")
        indexes = [
            models.Index(fields=["job", "cluster_index"]),
        ]

    def __str__(self):
        return f"{self.label} ({self.chunk_count} chunks)"


class RokunoheMinuteThemeChunk(models.Model):
    """
    六戸町会議録テーマ分析でクラスタへ割り当てられたチャンクを管理するモデル。

    1つの分析ジョブが完了結果として保存する、Chromaチャンクごとのテーマ所属です。
    `chunk_id` 単位でレコードはできますが、これは「このチャンクの処理がrunning」
    という進捗管理ではありません。ジョブ完了後に、ビューアで元チャンクへ
    テーマクラスタを紐づけるための結果テーブルです。

    Attributes:
        job: このチャンク分析を生成した分析ジョブ。
        cluster: このチャンクが属するテーマクラスタ。
        chunk_id: Chroma DB上のチャンクID。
        source: 出典PDFファイル名。
        source_date: 出典PDFファイル名から取得したYYYYMMDD形式の日付。
        page: PDF内のページ番号。
        chunk_index: RAG登録時のチャンク番号。
        candidate_labels: LLMがチャンク単位で抽出した候補テーマラベル。
        character_count: チャンク本文の文字数。
        created_at: レコードの作成日時。
    """

    job = models.ForeignKey(
        RokunoheMinuteThemeAnalysisJob,
        verbose_name="分析ジョブ",
        related_name="theme_chunks",
        on_delete=models.CASCADE,
    )
    cluster = models.ForeignKey(
        RokunoheMinuteThemeCluster,
        verbose_name="テーマクラスタ",
        related_name="theme_chunks",
        on_delete=models.CASCADE,
    )
    chunk_id = models.CharField(
        verbose_name="チャンクID",
        max_length=512,
        db_collation="utf8mb4_bin",
    )
    source = models.CharField(verbose_name="出典PDF", max_length=512, blank=True)
    source_date = models.CharField(verbose_name="出典日", max_length=8, blank=True)
    page = models.PositiveIntegerField(verbose_name="ページ番号", null=True, blank=True)
    chunk_index = models.PositiveIntegerField(
        verbose_name="チャンク番号",
        null=True,
        blank=True,
    )
    candidate_labels = models.JSONField(
        verbose_name="候補テーマラベル",
        default=list,
        blank=True,
    )
    character_count = models.PositiveIntegerField(verbose_name="文字数", default=0)
    created_at = models.DateTimeField(verbose_name="作成日時", auto_now_add=True)

    class Meta:
        db_table = "llm_chat_rokunohe_minute_theme_chunk"
        verbose_name = "六戸町会議録テーマチャンク"
        verbose_name_plural = "六戸町会議録テーマチャンク一覧"
        unique_together = ("job", "chunk_id")
        indexes = [
            models.Index(fields=["job", "chunk_id"]),
            models.Index(fields=["cluster", "source_date"]),
        ]

    def __str__(self):
        return self.chunk_id
