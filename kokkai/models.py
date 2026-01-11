from django.db import models


class MeetingIndex(models.Model):
    date = models.DateField(unique=True, verbose_name="開催日")
    count = models.IntegerField(default=0, verbose_name="件数")
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.date} : {self.count}件"
