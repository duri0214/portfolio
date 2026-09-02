import uuid

from django.db import models


class Meeting(models.Model):
    """
    国会会議録のメタデータと、必要に応じて取得した発言を管理するモデル。

    Attributes:
        meeting_date: 開催日。
        session_number: 国会回次。
        house: 院名。
        committee: 会議名。
        meeting_number: 号数。
        min_id: 国会会議録検索システムの会議録ID。
        url: 会議録テキストのURL。
        pdf_url: 会議録PDFのURL。
        created_at: レコード作成日時。
    """

    meeting_date = models.DateField("開催日", db_index=True)

    session_number = models.IntegerField("国会回次")
    house = models.CharField("院名", max_length=32)
    committee = models.CharField("会議名", max_length=128)
    meeting_number = models.CharField("号数", max_length=32)

    min_id = models.CharField("会議録ID", max_length=64)
    url = models.URLField("会議録URL")
    pdf_url = models.URLField("PDF URL", blank=True)
    is_current_catalog = models.BooleanField(
        "現在のカタログ", default=True, db_index=True
    )

    created_at = models.DateTimeField("作成日時", auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["min_id"], name="unique_meeting_min_id")
        ]


class Speech(models.Model):
    """
    全文取得済みの国会会議録に含まれる1発言を管理するモデル。

    Attributes:
        meeting: 所属する会議録。
        speaker_name: 発言者名。
        speaker_role: 発言者の役割。
        speaker_affiliation: 発言者の所属会派。
        speech_text: 発言本文。
        speech_order: 会議録内の発言順。
        created_at: レコード作成日時。
    """

    meeting = models.ForeignKey(
        Meeting,
        on_delete=models.CASCADE,
        related_name="speeches",
        verbose_name="会議録",
    )
    speaker_name = models.CharField("発言者名", max_length=128)
    speaker_role = models.CharField("発言者役割", max_length=128, null=True, blank=True)
    speaker_affiliation = models.CharField(
        "発言者所属会派", max_length=128, null=True, blank=True
    )
    speech_text = models.TextField("発言本文")
    speech_order = models.IntegerField("発言順")
    source_url = models.URLField("発言URL", blank=True)
    created_at = models.DateTimeField("作成日時", auto_now_add=True)


class MeetingScenario(models.Model):
    """会議録から生成した、再利用可能な選択式ゲームシナリオ。"""

    class Status(models.TextChoices):
        READY = "ready", "利用可能"
        FAILED = "failed", "生成失敗"

    meeting = models.ForeignKey(
        Meeting,
        on_delete=models.CASCADE,
        related_name="scenarios",
        verbose_name="会議録",
    )
    version = models.PositiveIntegerField("バージョン")
    source_hash = models.CharField("元データハッシュ", max_length=64, db_index=True)
    prompt_version = models.CharField("プロンプトバージョン", max_length=64)
    generator_model = models.CharField("生成モデル", max_length=64)
    status = models.CharField(
        "状態", max_length=16, choices=Status.choices, default=Status.READY
    )
    title = models.CharField("シナリオタイトル", max_length=200)
    overview = models.TextField("会議全体の要約")
    success_label = models.CharField("成功時の判定", max_length=64)
    failure_label = models.CharField("失敗時の判定", max_length=64)
    judgment_criteria = models.TextField("判定条件")
    passing_score = models.PositiveSmallIntegerField("合格点", default=50)
    generated_at = models.DateTimeField("生成日時", auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["meeting", "version"], name="unique_meeting_scenario_version"
            )
        ]
        indexes = [
            models.Index(
                fields=["meeting", "source_hash", "prompt_version", "status"],
                name="kokkai_scenario_cache_idx",
            )
        ]
        ordering = ["-version"]


class ScenarioActor(models.Model):
    """シナリオ内で選択できる会議参加アクター。"""

    scenario = models.ForeignKey(
        MeetingScenario,
        on_delete=models.CASCADE,
        related_name="actors",
        verbose_name="シナリオ",
    )
    display_order = models.PositiveIntegerField("表示順")
    name = models.CharField("氏名", max_length=128)
    role = models.CharField("役職", max_length=128, blank=True)
    affiliation = models.CharField("所属", max_length=128, blank=True)
    speech_count = models.PositiveIntegerField("発言数", default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["scenario", "name", "role", "affiliation"],
                name="unique_scenario_actor_identity",
            )
        ]
        ordering = ["display_order"]


class ScenarioTurn(models.Model):
    """根拠となる一次発言に対応するシナリオの1ターン。"""

    scenario = models.ForeignKey(
        MeetingScenario,
        on_delete=models.CASCADE,
        related_name="turns",
        verbose_name="シナリオ",
    )
    turn_number = models.PositiveIntegerField("ターン番号")
    actor = models.ForeignKey(
        ScenarioActor,
        on_delete=models.PROTECT,
        related_name="turns",
        verbose_name="発言アクター",
    )
    dialogue = models.TextField("会話文")
    evidence_speech = models.ForeignKey(
        Speech,
        on_delete=models.PROTECT,
        related_name="scenario_turns",
        verbose_name="根拠発言",
    )
    evidence_note = models.TextField("根拠の説明")

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["scenario", "turn_number"], name="unique_scenario_turn_number"
            )
        ]
        ordering = ["turn_number"]


class ScenarioChoice(models.Model):
    """ユーザー担当アクターのターンで選択する二択。"""

    play = models.ForeignKey(
        "ScenarioPlay",
        on_delete=models.SET_NULL,
        related_name="choices",
        null=True,
        blank=True,
        verbose_name="プレイ",
    )
    turn = models.ForeignKey(
        ScenarioTurn,
        on_delete=models.CASCADE,
        related_name="choices",
        verbose_name="ターン",
    )
    choice_number = models.PositiveSmallIntegerField("選択肢番号")
    text = models.TextField("選択肢")
    is_correct = models.BooleanField("適切な選択")
    rationale = models.TextField("選択根拠")
    prompt_version = models.CharField(
        "選択肢プロンプトバージョン", max_length=64, null=True, blank=True
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["play", "turn", "choice_number", "prompt_version"],
                name="unique_scenario_play_choice_version_number",
            )
        ]
        ordering = ["choice_number"]


class ScenarioPlay(models.Model):
    """選択したアクターで進める1回分のシナリオプレイ。"""

    play_id = models.UUIDField(
        "プレイID", default=uuid.uuid4, editable=False, unique=True
    )
    scenario = models.ForeignKey(
        MeetingScenario,
        on_delete=models.PROTECT,
        related_name="plays",
        verbose_name="シナリオ",
    )
    selected_actor = models.ForeignKey(
        ScenarioActor,
        on_delete=models.PROTECT,
        related_name="plays",
        verbose_name="担当アクター",
    )
    next_turn_number = models.PositiveIntegerField("次のターン番号", default=1)
    score = models.PositiveIntegerField("正解数", default=0)
    answer_count = models.PositiveIntegerField("回答数", default=0)
    result_label = models.CharField("最終判定", max_length=64, blank=True)
    result_explanation = models.TextField("最終判定の説明", blank=True)
    started_at = models.DateTimeField("開始日時", auto_now_add=True)
    completed_at = models.DateTimeField("終了日時", null=True, blank=True)

    @property
    def is_completed(self) -> bool:
        return self.completed_at is not None


class ScenarioPlayAnswer(models.Model):
    """プレイ中に選択した回答を保存し、再生時の外部API呼び出しをなくす。"""

    play = models.ForeignKey(
        ScenarioPlay,
        on_delete=models.CASCADE,
        related_name="answers",
        verbose_name="プレイ",
    )
    turn = models.ForeignKey(
        ScenarioTurn,
        on_delete=models.PROTECT,
        related_name="play_answers",
        verbose_name="ターン",
    )
    choice = models.ForeignKey(
        ScenarioChoice,
        on_delete=models.PROTECT,
        related_name="play_answers",
        verbose_name="選択肢",
    )
    selected_at = models.DateTimeField("選択日時", auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["play", "turn"], name="unique_play_turn_answer"
            )
        ]
