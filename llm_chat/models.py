from django.contrib.auth.models import User
from django.db import models

from lib.llm.valueobject.completion import RoleType


class ChatLogs(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=9,
        choices=[(x.name, x.value) for x in RoleType],
    )
    content = models.TextField()
    file = models.FileField(upload_to="llm_chat/audios/", null=True, blank=True)
    invisible = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
