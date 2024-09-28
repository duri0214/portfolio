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
    title = models.CharField(max_length=200)
    image = models.ImageField(upload_to=get_random_filename, blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    summary = models.TextField(blank=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
