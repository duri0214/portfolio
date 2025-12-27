from django.db import models


class RssSource(models.Model):
    name = models.CharField(max_length=100)
    url = models.URLField(unique=True)
    category = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    last_fetched_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class RssFeed(models.Model):
    source = models.ForeignKey(
        RssSource, on_delete=models.CASCADE, related_name="feeds"
    )
    title = models.CharField(max_length=500)
    summary = models.TextField(blank=True)
    link = models.URLField(max_length=500, unique=True)
    published_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-published_at"]

    def __str__(self):
        return self.title
