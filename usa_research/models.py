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


class Sector(models.Model):
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.name} ({self.symbol})"


class SectorDailySnapshot(models.Model):
    date = models.DateField()
    sector = models.ForeignKey(
        Sector, on_delete=models.CASCADE, related_name="snapshots"
    )
    rs_20d = models.FloatField()
    rs_slope_5d = models.FloatField()
    rank = models.IntegerField()
    rank_delta_5d = models.IntegerField()
    signal = models.CharField(max_length=10)

    class Meta:
        unique_together = ("date", "sector")
        ordering = ["-date", "rank"]

    def __str__(self):
        return f"{self.date} - {self.sector.name} - Rank: {self.rank}"


class MacroIndicator(models.Model):
    date = models.DateField(unique=True)

    ism_pmi = models.FloatField(null=True, blank=True)
    us_10y_yield = models.FloatField(null=True, blank=True)
    vix = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.date} - PMI: {self.ism_pmi}, 10Y: {self.us_10y_yield}, VIX: {self.vix}"
