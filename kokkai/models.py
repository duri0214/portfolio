from django.db import models


class Meeting(models.Model):
    meeting_date = models.DateField(db_index=True)

    session_number = models.IntegerField()  # 219
    house = models.CharField(max_length=32)  # 衆議院 / 参議院
    committee = models.CharField(max_length=128)
    meeting_number = models.CharField(max_length=32)  # 第5号

    agenda_title = models.TextField()  # 議題名
    agenda_order = models.IntegerField()

    min_id = models.CharField(max_length=64)
    url = models.URLField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["min_id", "agenda_order"], name="unique_meeting_agenda"
            )
        ]


class Speech(models.Model):
    meeting = models.ForeignKey(
        Meeting, on_delete=models.CASCADE, related_name="speeches"
    )

    speaker_name = models.CharField(max_length=128)
    speaker_role = models.CharField(max_length=128, null=True, blank=True)
    speaker_affiliation = models.CharField(max_length=128, null=True, blank=True)

    speech_text = models.TextField()
    speech_order = models.IntegerField()

    created_at = models.DateTimeField(auto_now_add=True)
