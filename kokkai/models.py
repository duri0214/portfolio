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
    created_at = models.DateTimeField("作成日時", auto_now_add=True)
