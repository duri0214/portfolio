from django.db import models


class Category(models.Model):
    name = models.CharField(max_length=200)


class Post(models.Model):
    title = models.CharField(max_length=200)
    image = models.ImageField(upload_to="home/posts/", blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE)
    summary = models.TextField(blank=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)
