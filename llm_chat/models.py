from django.contrib.auth.models import User
from django.db import models


class ChatLogsWithLine(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(max_length=255)
    content = models.TextField()
    file_path = models.CharField(max_length=255, null=True)
    invisible = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
