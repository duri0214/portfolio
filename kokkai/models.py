from django.db import models


class Meeting(models.Model):
    meeting_date = models.DateField(db_index=True)

    session_number = models.IntegerField()
    house = models.CharField(max_length=32)
    committee = models.CharField(max_length=128)
    meeting_number = models.CharField(max_length=32)

    min_id = models.CharField(max_length=64)
    url = models.URLField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["min_id"], name="unique_meeting_min_id")
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
