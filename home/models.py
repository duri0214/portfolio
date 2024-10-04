import os
import uuid

from django.db import models


def get_random_filename(instance, filename):
    ext = filename.split(".")[-1]
    filename = f"{uuid.uuid4()}.{ext}"
    return os.path.join("home/posts/", filename)


class Category(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class Post(models.Model):
    title = models.CharField(verbose_name="記事タイトル", max_length=200)
    image = models.ImageField(
        verbose_name="画像", upload_to=get_random_filename, blank=True, null=True
    )
    category = models.ForeignKey(
        Category, verbose_name="記事カテゴリー", on_delete=models.CASCADE
    )
    summary = models.TextField(verbose_name="記事概要")
    content = models.TextField(verbose_name="記事内容")
    is_featured = models.BooleanField(
        verbose_name="ピックアップ記事として選択", default=False
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
