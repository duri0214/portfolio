"""models.py"""
from django.db import models

class LinePush(models.Model):
    """Lineでのプッシュ先を表す"""
    user_id = models.CharField(max_length=100, unique=True)

    def __str__(self):
        return self.user_id
