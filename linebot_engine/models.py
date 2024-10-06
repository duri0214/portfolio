from django.db import models


class UserProfile(models.Model):
    """
    フォローしたときにLINEプラットフォームでやりとりされるユーザ情報を保存する
    ブロックされたときは削除する
    """

    line_user_id = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=100, null=True)
    picture = models.ImageField(upload_to="linebot_engine/images/", null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return self.line_user_id


class Message(models.Model):
    user_profile = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    source_type = models.CharField(max_length=100)
    message = models.TextField()
    picture = models.ImageField(upload_to="linebot_engine/images/", null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
