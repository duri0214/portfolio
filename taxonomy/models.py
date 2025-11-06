from django.db import models


class JmaWeatherCode(models.Model):
    """
    天気コードマスタ（taxonomy にローカライズ）

    Attributes:
        code (CharField): "123"
        summary_code (CharField): "100"
        image (CharField): "100.svg"
        name (CharField): "晴"
        name_en (CharField): "CLEAR, FREQUENT SNOW FLURRIES LATER"
    """

    code = models.CharField(unique=True, max_length=3)
    summary_code = models.CharField(max_length=3)
    image = models.CharField(max_length=7)
    name = models.CharField(max_length=20)
    name_en = models.CharField(max_length=100)


class Kingdom(models.Model):
    """
    界マスタ
    """

    name = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class Phylum(models.Model):
    """
    門マスタ フィラムと読む
    """

    name = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)
    kingdom = models.ForeignKey(Kingdom, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class Classification(models.Model):
    """
    綱マスタ コウと読む
    """

    name = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)
    phylum = models.ForeignKey(Phylum, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class Family(models.Model):
    """
    科マスタ
    """

    name = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)
    classification = models.ForeignKey(Classification, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class Genus(models.Model):
    """
    属マスタ
    """

    name = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)
    family = models.ForeignKey(Family, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class Species(models.Model):
    """
    種マスタ
    """

    name = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)
    genus = models.ForeignKey(Genus, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class NaturalMonument(models.Model):
    """
    天然記念物区分
    """

    name = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class Tag(models.Model):
    """
    タグマスタ
    """

    name = models.CharField(max_length=20)
    remark = models.CharField(max_length=255, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class Breed(models.Model):
    """
    品種
    """

    name = models.CharField(max_length=255)
    name_kana = models.CharField(max_length=255)
    image = models.ImageField(upload_to="taxonomy/breed")
    remark = models.CharField(max_length=255, null=True)
    natural_monument = models.ForeignKey(
        NaturalMonument, on_delete=models.CASCADE, null=True
    )
    species = models.ForeignKey(Species, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["species", "name"], name="species_name_unique"
            )
        ]


class BreedTags(models.Model):
    """
    品種のタグ
    """

    breed = models.ForeignKey(Breed, on_delete=models.CASCADE)
    tag = models.ForeignKey(Tag, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["breed", "tag"], name="breed_tag_unique")
        ]


class FeedGroup(models.Model):
    """
    モデル: 飼料重量マスタ

    飼料重量とその分類名を保持するマスタデータ。
    """

    name = models.CharField(max_length=50, unique=True)
    weight = models.IntegerField(unique=True, help_text="飼料の重量 (単位: g)")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)

    def __str__(self):
        return f"{self.name} （{self.weight}g）"


class HenGroup(models.Model):
    name = models.CharField(max_length=100, unique=True)
    hen_count = models.IntegerField()
    remark = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)

    def __str__(self):
        return f"{self.name} ({self.hen_count}羽)"


class EggLedger(models.Model):
    """
    モデル: 鶏の産卵台帳 (Egg Ledger)
    """

    recorded_date = models.DateField()
    egg_count = models.IntegerField(null=True, blank=True)  # 産卵数 (単位: 個)
    avg_egg_weight = models.FloatField(null=True, blank=True)  # 平均卵重 (単位: g)
    temperature = models.FloatField(null=True, blank=True)  # 気温 (単位: °C)
    humidity = models.FloatField(null=True, blank=True)  # 湿度 (単位: %)
    rainfall = models.FloatField(null=True, blank=True)  # 降水量 (単位: mm)
    air_pressure = models.FloatField(null=True, blank=True)  # 気圧 (単位: hPa)
    comment = models.TextField(null=True, blank=True)  # 作業者のコメントなど

    weather_code = models.ForeignKey(JmaWeatherCode, on_delete=models.PROTECT)
    feed_group = models.ForeignKey(FeedGroup, on_delete=models.CASCADE)
    hen_group = models.ForeignKey(HenGroup, on_delete=models.CASCADE)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)

    def laying_rate(self):
        # egg_countやhen_groupがNoneの場合はゼロ埋めする
        egg_count = self.egg_count or 0
        hen_count = (
            self.hen_group.hen_count
            if self.hen_group and self.hen_group.hen_count
            else 0
        )

        # hen_countがゼロの時、ゼロ除算を防ぐ
        if hen_count == 0:
            return 0

        # レート計算
        return round((egg_count / hen_count) * 100, 2)

    def __str__(self):
        return (
            f"{self.recorded_date} - {self.hen_group.name}: "
            f"{self.egg_count}個, {self.laying_rate()}%"
        )
