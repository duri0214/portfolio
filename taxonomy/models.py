from django.db import models


class Kingdom(models.Model):
    """
    界マスタ
    """

    name = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)

    class Meta:
        db_table = "taxonomy_m_kingdom"


class Phylum(models.Model):
    """
    門マスタ フィラムと読む
    """

    name = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)
    kingdom = models.ForeignKey(Kingdom, on_delete=models.CASCADE)

    class Meta:
        db_table = "taxonomy_m_phylum"


class Classification(models.Model):
    """
    綱マスタ コウと読む
    """

    name = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)
    phylum = models.ForeignKey(Phylum, on_delete=models.CASCADE)

    class Meta:
        db_table = "taxonomy_m_classification"


class Family(models.Model):
    """
    科マスタ
    """

    name = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)
    classification = models.ForeignKey(Classification, on_delete=models.CASCADE)

    class Meta:
        db_table = "taxonomy_m_family"


class Genus(models.Model):
    """
    属マスタ
    """

    name = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)
    family = models.ForeignKey(Family, on_delete=models.CASCADE)

    class Meta:
        db_table = "taxonomy_m_genus"


class Species(models.Model):
    """
    種マスタ
    """

    name = models.CharField(max_length=255)
    name_en = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)
    genus = models.ForeignKey(Genus, on_delete=models.CASCADE)

    class Meta:
        db_table = "taxonomy_m_species"


class NaturalMonument(models.Model):
    """
    天然記念物区分
    """

    name = models.CharField(max_length=255)
    remark = models.CharField(max_length=255, null=True)

    class Meta:
        db_table = "taxonomy_m_natural_monument"


class Tag(models.Model):
    """
    タグマスタ
    """

    name = models.CharField(max_length=20)
    remark = models.CharField(max_length=255, null=True)

    class Meta:
        db_table = "taxonomy_m_tag"


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


class EggProductionRecord(models.Model):
    """
    モデル: 鶏の産卵記録

    このモデルは、特定の日における鶏の産卵記録を保持します。
    主に天気、気象データ、産卵数などの情報を追跡します。
    """

    recorded_date = models.DateField(
        help_text="データを記録した日付 (形式: YYYY-MM-DD)"
    )
    weather_code = models.IntegerField(
        help_text="天気コード。具体的なコードの詳細はシステムで管理"
    )
    avg_temperature = models.FloatField(help_text="平均気温 (単位: °C)", null=True)
    humidity = models.FloatField(help_text="湿度 (単位: %)", null=True)
    pressure = models.FloatField(help_text="気圧 (単位: hPa)", null=True)
    rainfall = models.FloatField(help_text="降水量 (単位: mm)", null=True)
    hen_count = models.IntegerField(help_text="メスの個体数 (単位: 羽)")
    egg_count = models.IntegerField(help_text="産卵数 (単位: 個)", null=True)
    avg_egg_weight = models.FloatField(help_text="卵の平均重量 (単位: g)", null=True)
    feed_weight = models.IntegerField(
        help_text="消費した飼料の量 (単位: 125g／升)", null=True
    )
    comment = models.TextField(
        blank=True,
        null=True,
        help_text="自由記述フィールド。産卵に関するコメントや観察記録を記入",
    )

    def laying_rate(self):
        """
        メスの鶏1羽あたりの産卵率を計算します。

        Returns:
            float: メスの鶏あたりの産卵率 (百分率で表示)
        """
        if self.hen_count > 0:
            return round((self.egg_count / self.hen_count) * 100, 2)
        return 0.0

    def __str__(self):
        """
        インスタンスを文字列として表現します。

        Returns:
            str: 記録された日付と産卵状況の概要。
        """
        return f"{self.recorded_date} ({self.hen_count}羽, {self.egg_count}個, {self.laying_rate()}%)"
