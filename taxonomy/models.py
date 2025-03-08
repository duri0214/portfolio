from django.db import models

from soil_analysis.models import JmaWeatherCode


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


class FeedWeight(models.Model):
    """
    モデル: 飼料重量マスタ

    飼料重量とその分類名を保持するマスタデータ。
    """

    name = models.CharField(
        max_length=50,
        unique=True,
        help_text="飼料重量に対応する名前 (例: 通常量, 少量)",
    )

    weight = models.IntegerField(unique=True, help_text="飼料の重量 (単位: g)")

    def __str__(self):
        return f"{self.name} ({self.weight}g)"


class HenGroup(models.Model):
    """
    モデル: 鶏のグループマスタ

    鶏の羽数やメモなどをグループ単位で管理できるマスタテーブル。
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="鶏グループの名前 (例: 農場A, ロット1など)",
    )
    hen_count = models.IntegerField(
        help_text="このグループ内のメスの鶏の羽数 (単位: 羽)"
    )
    remark = models.TextField(blank=True, null=True, help_text="備考や補足説明")

    def __str__(self):
        return f"{self.name} ({self.hen_count}羽)"


class EggLedger(models.Model):
    """
    モデル: 鶏の産卵台帳 (Egg Ledger)

    天気の気温や湿度、降水量などと産卵情報を記録。
    """

    hen_group = models.ForeignKey(
        HenGroup,
        on_delete=models.PROTECT,
        help_text="この記録に該当する鶏グループとのリレーション",
    )
    recorded_date = models.DateField(
        help_text="データを記録した日付 (形式: YYYY-MM-DD)"
    )
    weather_code = models.ForeignKey(
        JmaWeatherCode,
        on_delete=models.PROTECT,
        to_field="code",
        help_text="天気コード。天気マスタ (JmaWeatherCode)とのリレーション",
    )
    temperature = models.FloatField(help_text="気温 (単位: °C)", null=True)
    humidity = models.FloatField(help_text="湿度 (単位: %)", null=True)
    pressure = models.FloatField(help_text="気圧 (単位: hPa)", null=True)
    rainfall = models.FloatField(help_text="降水量 (単位: mm)", null=True)
    egg_count = models.IntegerField(help_text="産卵数 (単位: 個)", null=True)
    avg_egg_weight = models.FloatField(help_text="卵の平均重量 (単位: g)", null=True)
    feed_weight = models.ForeignKey(
        FeedWeight,
        on_delete=models.PROTECT,
        help_text="飼料の重量マスタ（飼料重量と分類名）とのリレーション",
    )
    comment = models.TextField(
        blank=True,
        null=True,
        help_text="自由記述フィールド。産卵に関するコメントや観察記録を記入",
    )

    def laying_rate(self):
        if self.hen_group and self.hen_group.hen_count > 0:
            return round((self.egg_count / self.hen_group.hen_count) * 100, 2)
        return 0.0

    def __str__(self):
        return (
            f"{self.recorded_date} - {self.hen_group.name}: "
            f"{self.egg_count}個, {self.laying_rate()}%"
        )
