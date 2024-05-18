from django.db import models


class UserProfile(models.Model):
    """Lineでのプッシュ先を表す"""

    user_id = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=100, null=True)
    picture = models.ImageField(upload_to="linebot_engine/", null=True)

    def __str__(self):
        return self.user_id
